"""Exportação para Excel (XlsxWriter)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import xlsxwriter

from ..chave import formatar_cnpj
from ..consultas import FiltroNotas, FiltroPendencias, kpis, listar_notas, listar_pendencias, rotulo_periodo
from ..rules import NIVEL_ROTULO, REGRAS
from ..sefaz import ResultadoConferencia

AZUL = "#16233A"
DOURADO = "#B08A4A"


class _Formatos:
    def __init__(self, wb: xlsxwriter.Workbook):
        self.titulo = wb.add_format({"bold": True, "font_size": 18, "font_color": AZUL, "font_name": "Calibri"})
        self.subtitulo = wb.add_format({"font_size": 10, "font_color": "#5E6675", "font_name": "Calibri"})
        self.cab = wb.add_format({"bold": True, "font_color": "white", "bg_color": AZUL, "border": 0,
                                  "font_name": "Calibri", "valign": "vcenter", "text_wrap": True})
        self.texto = wb.add_format({"font_name": "Calibri", "valign": "top"})
        self.quebra = wb.add_format({"font_name": "Calibri", "valign": "top", "text_wrap": True})
        self.moeda = wb.add_format({"num_format": "#,##0.00", "font_name": "Calibri"})
        self.inteiro = wb.add_format({"num_format": "0", "font_name": "Calibri"})
        self.data = wb.add_format({"num_format": "dd/mm/yyyy", "font_name": "Calibri"})
        self.rotulo = wb.add_format({"font_name": "Calibri", "font_color": "#5E6675"})
        self.kpi = wb.add_format({"bold": True, "font_size": 14, "font_color": AZUL, "font_name": "Calibri",
                                  "num_format": "#,##0"})
        self.kpi_moeda = wb.add_format({"bold": True, "font_size": 14, "font_color": AZUL, "font_name": "Calibri",
                                        "num_format": "R$ #,##0.00"})
        self.alta = wb.add_format({"font_color": "#A4483A", "bold": True, "font_name": "Calibri"})
        self.media = wb.add_format({"font_color": "#94692A", "bold": True, "font_name": "Calibri"})
        self.baixa = wb.add_format({"font_color": "#3D5A80", "font_name": "Calibri"})


def _data(texto: str):
    try:
        return datetime.strptime(texto[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _reais(centavos: int | None) -> float:
    return round((centavos or 0) / 100, 2)


def _tabela(ws, f: _Formatos, linha0: int, cabecalhos: list[tuple[str, int, str]], linhas: list[list]) -> None:
    """Escreve uma tabela com filtros. cabecalhos: (título, largura, tipo)."""
    for col, (titulo, largura, _tipo) in enumerate(cabecalhos):
        ws.write(linha0, col, titulo, f.cab)
        ws.set_column(col, col, largura)
    ws.set_row(linha0, 30)
    for i, valores in enumerate(linhas, start=linha0 + 1):
        for col, ((_t, _l, tipo), valor) in enumerate(zip(cabecalhos, valores)):
            if tipo == "moeda":
                ws.write_number(i, col, valor or 0, f.moeda)
            elif tipo == "int":
                ws.write_number(i, col, valor or 0, f.inteiro)
            elif tipo == "data":
                d = _data(valor)
                if d:
                    ws.write_datetime(i, col, d, f.data)
                else:
                    ws.write(i, col, valor or "", f.texto)
            elif tipo == "quebra":
                ws.write(i, col, valor or "", f.quebra)
            else:
                ws.write_string(i, col, str(valor if valor is not None else ""), f.texto)
    if linhas:
        ws.autofilter(linha0, 0, linha0 + len(linhas), len(cabecalhos) - 1)
    ws.freeze_panes(linha0 + 1, 0)


def exportar_relatorio(con: sqlite3.Connection, destino: str | Path, cnpj: str | None = None,
                       ano_mes: str | None = None, nome_cliente: str = "") -> Path:
    destino = Path(destino)
    wb = xlsxwriter.Workbook(str(destino))
    f = _Formatos(wb)

    notas = listar_notas(con, FiltroNotas(cnpj=cnpj, ano_mes=ano_mes, limite=1_000_000))
    notas = [n for n in notas if n["tp_amb"] == 1]
    chaves = [n["chave"] for n in notas]
    pend = listar_pendencias(con, FiltroPendencias(cnpj=cnpj, ano_mes=ano_mes, situacao="todas"))

    # ---------------- Resumo
    ws = wb.add_worksheet("Resumo")
    ws.hide_gridlines(2)
    ws.set_column(0, 0, 34)
    ws.set_column(1, 1, 22)
    ws.write(0, 0, "Conferi AI · Relatório de notas", f.titulo)
    escopo = nome_cliente or "Todos os clientes"
    ws.write(1, 0, f"{escopo} · {rotulo_periodo(ano_mes)} · gerado em {datetime.now():%d/%m/%Y %H:%M}", f.subtitulo)
    k = kpis(con, ano_mes) if not cnpj else None
    ativas = [n for n in notas if not n["cancelada"]]
    if cnpj:
        faturamento = sum(n["v_nf"] for n in ativas if n["emit_doc"] == cnpj and n["tp_nf"] == 1 and n["fin_nfe"] != 4)
        compras = sum(n["v_nf"] for n in ativas if n["dest_doc"] == cnpj and n["tp_nf"] == 1)
    else:
        faturamento, compras = k.faturamento, k.compras
    abertas = [p for p in pend if p["situacao"] == "aberta" and p["nivel"] != "info"]
    linhas_resumo = [
        ("Notas no período", len(notas), f.kpi),
        ("Notas canceladas", sum(1 for n in notas if n["cancelada"]), f.kpi),
        ("Faturamento (saídas não canceladas)", _reais(faturamento), f.kpi_moeda),
        ("Compras (entradas não canceladas)", _reais(compras), f.kpi_moeda),
        ("Pendências abertas — alta", sum(1 for p in abertas if p["nivel"] == "alta"), f.kpi),
        ("Pendências abertas — média", sum(1 for p in abertas if p["nivel"] == "media"), f.kpi),
        ("Pendências abertas — baixa", sum(1 for p in abertas if p["nivel"] == "baixa"), f.kpi),
    ]
    for i, (rotulo, valor, fmt) in enumerate(linhas_resumo, start=3):
        ws.write(i, 0, rotulo, f.rotulo)
        ws.write(i, 1, valor, fmt)
    ws.write(11, 0, "Os alertas são pontos para conferência e não substituem a análise do profissional responsável.",
             f.subtitulo)

    # ---------------- Notas
    ws = wb.add_worksheet("Notas")
    cab = [("Data", 11, "data"), ("Modelo", 8, "txt"), ("Série", 6, "int"), ("Número", 10, "int"),
           ("Emitente", 32, "txt"), ("CNPJ emitente", 19, "txt"), ("Destinatário", 32, "txt"),
           ("CNPJ/CPF destinatário", 19, "txt"), ("UF dest.", 7, "txt"), ("CFOP principal", 9, "txt"),
           ("Natureza da operação", 26, "txt"), ("Produtos", 13, "moeda"), ("Desconto", 11, "moeda"),
           ("Frete", 11, "moeda"), ("ICMS", 11, "moeda"), ("Total da nota", 14, "moeda"), ("Situação", 11, "txt"),
           ("Chave de acesso", 47, "txt")]
    _tabela(ws, f, 0, cab, [
        [n["data_emissao"], "NFC-e" if n["modelo"] == "65" else "NF-e", n["serie"], n["numero"], n["emit_nome"],
         formatar_cnpj(n["emit_doc"]), n["dest_nome"], formatar_cnpj(n["dest_doc"]), n["dest_uf"], n["cfop_principal"],
         n["nat_op"], _reais(n["v_prod"]), _reais(n["v_desc"]), _reais(n["v_frete"]), _reais(n["v_icms"]),
         _reais(n["v_nf"]), "Cancelada" if n["cancelada"] else "Ativa", n["chave"]]
        for n in notas
    ])

    # ---------------- Itens
    ws = wb.add_worksheet("Itens")
    cab = [("Data", 11, "data"), ("Número", 10, "int"), ("Emitente", 30, "txt"), ("Destinatário", 30, "txt"),
           ("Item", 6, "int"), ("Código", 12, "txt"), ("Descrição", 40, "txt"), ("NCM", 10, "txt"), ("CFOP", 7, "txt"),
           ("Unid.", 6, "txt"), ("Quantidade", 11, "txt"), ("Valor unitário", 13, "txt"), ("Valor total", 13, "moeda"),
           ("IBS/CBS", 9, "txt"), ("Situação da nota", 12, "txt")]
    info = {n["chave"]: n for n in notas}
    linhas = []
    for lote in range(0, len(chaves), 900):
        parte = chaves[lote:lote + 900]
        marcadores = ",".join("?" * len(parte))
        for it in con.execute(f"SELECT * FROM itens WHERE chave IN ({marcadores}) ORDER BY chave, n_item", parte):
            n = info[it["chave"]]
            linhas.append([n["data_emissao"], n["numero"], n["emit_nome"], n["dest_nome"], it["n_item"], it["codigo"],
                           it["descricao"], it["ncm"], it["cfop"], it["unidade"], it["quantidade"], it["valor_unitario"],
                           _reais(it["v_prod"]), "Sim" if it["ibscbs_presente"] else "Não",
                           "Cancelada" if n["cancelada"] else "Ativa"])
    _tabela(ws, f, 0, cab, linhas)

    # ---------------- Resumos agregados (somente notas ativas)
    def agrupar(chave_func, valor_func):
        grupos: dict = {}
        for n in ativas:
            chave = chave_func(n)
            if chave is None:
                continue
            g = grupos.setdefault(chave, [0, 0])
            g[0] += 1
            g[1] += valor_func(n)
        return grupos

    ws = wb.add_worksheet("Por fornecedor")
    compras_por = agrupar(lambda n: (n["emit_nome"], formatar_cnpj(n["emit_doc"]))
                          if (not cnpj or n["dest_doc"] == cnpj) and n["tp_nf"] == 1 and n["dest_doc"] else None,
                          lambda n: n["v_nf"])
    _tabela(ws, f, 0, [("Fornecedor", 40, "txt"), ("CNPJ", 19, "txt"), ("Notas", 8, "int"), ("Valor", 15, "moeda")],
            [[a, b, q, _reais(v)] for (a, b), (q, v) in sorted(compras_por.items(), key=lambda x: -x[1][1])])

    ws = wb.add_worksheet("Por comprador")
    vendas_por = agrupar(lambda n: (n["dest_nome"] or "Consumidor final", formatar_cnpj(n["dest_doc"]))
                         if (not cnpj or n["emit_doc"] == cnpj) and n["tp_nf"] == 1 else None, lambda n: n["v_nf"])
    _tabela(ws, f, 0, [("Comprador", 40, "txt"), ("CNPJ/CPF", 19, "txt"), ("Notas", 8, "int"), ("Valor", 15, "moeda")],
            [[a, b, q, _reais(v)] for (a, b), (q, v) in sorted(vendas_por.items(), key=lambda x: -x[1][1])])

    ws = wb.add_worksheet("Por CFOP")
    por_cfop: dict[str, list[int]] = {}
    por_ncm: dict[str, list] = {}
    ativas_set = {n["chave"] for n in ativas}
    for lote in range(0, len(chaves), 900):
        parte = [c for c in chaves[lote:lote + 900] if c in ativas_set]
        if not parte:
            continue
        marcadores = ",".join("?" * len(parte))
        for it in con.execute(f"SELECT cfop, ncm, descricao, v_prod FROM itens WHERE chave IN ({marcadores})", parte):
            c = por_cfop.setdefault(it["cfop"], [0, 0])
            c[0] += 1
            c[1] += it["v_prod"]
            m = por_ncm.setdefault(it["ncm"], [0, 0, it["descricao"]])
            m[0] += 1
            m[1] += it["v_prod"]
    _tabela(ws, f, 0, [("CFOP", 8, "txt"), ("Itens", 8, "int"), ("Valor dos produtos", 18, "moeda")],
            [[c, q, _reais(v)] for c, (q, v) in sorted(por_cfop.items())])
    ws = wb.add_worksheet("Por NCM")
    _tabela(ws, f, 0, [("NCM", 10, "txt"), ("Exemplo de descrição", 40, "txt"), ("Itens", 8, "int"),
                       ("Valor dos produtos", 18, "moeda")],
            [[c, d, q, _reais(v)] for c, (q, v, d) in sorted(por_ncm.items(), key=lambda x: -x[1][1])])

    ws = wb.add_worksheet("Por mês")
    meses: dict[str, list[int]] = {}
    clientes = {cnpj} if cnpj else {r[0] for r in con.execute("SELECT cnpj FROM empresas WHERE is_cliente = 1")}
    for n in ativas:
        m = meses.setdefault(n["ano_mes"], [0, 0, 0, 0])
        if n["emit_doc"] in clientes or not clientes:
            m[0] += 1
            m[1] += n["v_nf"]
        if n["dest_doc"] in clientes:
            m[2] += 1
            m[3] += n["v_nf"]
    _tabela(ws, f, 0, [("Mês", 10, "txt"), ("Notas de saída", 14, "int"), ("Valor de saída", 16, "moeda"),
                       ("Notas de entrada", 15, "int"), ("Valor de entrada", 16, "moeda")],
            [[mes, a, _reais(b), c, _reais(d)] for mes, (a, b, c, d) in sorted(meses.items())])

    # ---------------- Pendências
    ws = wb.add_worksheet("Pendências")
    cab = [("Nível", 11, "txt"), ("Cliente", 30, "txt"), ("Modelo", 8, "txt"), ("Série", 6, "int"),
           ("Número", 10, "int"), ("Data", 11, "data"), ("Regra", 22, "txt"), ("Alerta", 46, "quebra"),
           ("Detalhe", 60, "quebra"), ("Situação", 11, "txt"), ("Chave de acesso", 47, "txt")]
    _tabela(ws, f, 0, cab, [
        [NIVEL_ROTULO.get(p["nivel"], p["nivel"]), p["empresa_nome"], "NFC-e" if p["modelo"] == "65" else "NF-e",
         p["serie"], p["numero"], p["data_ref"], REGRAS.get(p["regra"], p["regra"]), p["titulo"], p["detalhe"],
         p["situacao"].capitalize(), p["chave"]]
        for p in pend
    ])
    for i, p in enumerate(pend, start=1):
        fmt = {"alta": f.alta, "media": f.media, "baixa": f.baixa}.get(p["nivel"])
        if fmt:
            ws.write(i, 0, NIVEL_ROTULO[p["nivel"]], fmt)

    wb.close()
    return destino


def exportar_conferencia(resultado: ResultadoConferencia, destino: str | Path, nome_cliente: str = "") -> Path:
    destino = Path(destino)
    wb = xlsxwriter.Workbook(str(destino))
    f = _Formatos(wb)
    ws = wb.add_worksheet("Resumo")
    ws.hide_gridlines(2)
    ws.set_column(0, 0, 44)
    ws.set_column(1, 1, 12)
    ws.write(0, 0, "Conferi AI · Conferência com a Sefaz", f.titulo)
    ws.write(1, 0, f"{nome_cliente} · {formatar_cnpj(resultado.cnpj)} · {rotulo_periodo(resultado.ano_mes)}",
             f.subtitulo)
    grupos = [
        ("Na Sefaz, mas não recebidas pelo escritório", resultado.faltando_no_escritorio),
        ("Recebidas, mas fora da relação da Sefaz", resultado.fora_da_sefaz),
        ("Canceladas na Sefaz, ativas no escritório", resultado.cancelada_na_sefaz),
        ("Canceladas no escritório, autorizadas na Sefaz", resultado.cancelada_no_escritorio),
        ("Conferem", resultado.conferem),
    ]
    for i, (rotulo, lista) in enumerate(grupos, start=3):
        ws.write(i, 0, rotulo, f.rotulo)
        ws.write(i, 1, len(lista), f.kpi)
    cab = [("Modelo", 8, "txt"), ("Série", 6, "int"), ("Número", 10, "int"), ("Data", 11, "data"),
           ("Valor", 13, "moeda"), ("Situação na Sefaz", 16, "txt"), ("Situação no escritório", 18, "txt"),
           ("Chave de acesso", 47, "txt")]
    nomes = ["Faltando no escritório", "Fora da Sefaz", "Cancelada na Sefaz", "Cancelada no escritório", "Conferem"]
    for nome, (_r, lista) in zip(nomes, grupos):
        ws = wb.add_worksheet(nome)
        _tabela(ws, f, 0, cab, [
            ["NFC-e" if x.modelo == "65" else "NF-e", x.serie, x.numero, x.data, _reais(x.valor),
             x.situacao_sefaz.capitalize(), x.situacao_escritorio.capitalize(), x.chave] for x in lista
        ])
    wb.close()
    return destino
