"""Testa o fluxo completo com o cenário de demonstração e o gabarito."""

import gzip
import sqlite3
from pathlib import Path

import pytest
from openpyxl import load_workbook

from conferi.core import backup, clientes, consultas, db, sefaz
from conferi.core.config import ConfigRegras
from conferi.core.exporters.excel import exportar_conferencia, exportar_relatorio
from conferi.core.exporters.pdf import exportar_pendencias
from conferi.core.importer import importar
from conferi.core.rules import definir_situacao, recalcular_pendencias
from conferi.core.sources import FontePastasArquivos
from conferi.testing.cenario import DISTRIBUIDORA, LOJA, PADARIA, gerar_cenario


@pytest.fixture
def base(tmp_path):
    gabarito = gerar_cenario(tmp_path / "demo")
    con = db.abrir(tmp_path / "conferi.db")
    resultado = importar(con, FontePastasArquivos([tmp_path / "demo"]))
    clientes.confirmar_sugestoes_automaticamente(con)
    recalcular_pendencias(con, ConfigRegras())
    yield con, gabarito, resultado, tmp_path
    con.close()


def test_importacao_bate_com_gabarito(base):
    con, g, r, _ = base
    assert r.total_arquivos == g.arquivos_xml
    assert r.notas_novas == g.notas_unicas
    assert r.duplicadas == g.duplicadas
    assert r.notas_atualizadas == g.atualizadas
    assert r.eventos == g.eventos
    assert r.inutilizacoes == g.inutilizacoes
    assert len(r.invalidos) == g.invalidos
    assert len(r.ignorados) == g.ignorados
    assert con.execute("SELECT COUNT(*) FROM notas").fetchone()[0] == g.notas_unicas
    assert con.execute("SELECT COUNT(*) FROM notas WHERE cancelada = 1").fetchone()[0] == g.canceladas
    # a compra que chegou sem protocolo foi atualizada para a versão autorizada
    assert con.execute("SELECT n_prot FROM notas WHERE numero = 9100").fetchone()[0]


def test_reimportar_nao_duplica(base):
    con, g, _, tmp = base
    r2 = importar(con, FontePastasArquivos([tmp / "demo"]))
    assert r2.notas_novas == 0
    assert con.execute("SELECT COUNT(*) FROM notas").fetchone()[0] == g.notas_unicas


def test_sugestao_de_clientes(base):
    con, *_ = base
    confirmados = {r["cnpj"] for r in consultas.lista_clientes(con)}
    assert {PADARIA.cnpj, DISTRIBUIDORA.cnpj, LOJA.cnpj} <= confirmados
    assert len(confirmados) == 3


def test_pendencias_esperadas(base):
    con, g, *_ = base
    contagem = {r["regra"]: r["qtd"] for r in con.execute("SELECT regra, COUNT(*) AS qtd FROM pendencias GROUP BY regra")}
    for regra, minimo in g.pendencias_esperadas.items():
        assert contagem.get(regra, 0) == minimo, (regra, contagem)
    lacunas = {(r["cnpj_empresa"], r["numero"]) for r in con.execute("SELECT * FROM pendencias WHERE regra='sequencia'")}
    assert (PADARIA.cnpj, 1015) in lacunas      # 1022–1023 inutilizadas não aparecem
    assert (DISTRIBUIDORA.cnpj, 517) in lacunas


def test_situacao_sobrevive_ao_recalculo(base):
    con, *_ = base
    h = con.execute("SELECT hash FROM pendencias WHERE regra = 'total_nota'").fetchone()[0]
    definir_situacao(con, [h], "resolvida")
    recalcular_pendencias(con, ConfigRegras())
    abertas = consultas.listar_pendencias(con, consultas.FiltroPendencias(regra="total_nota"))
    assert abertas == []
    resolvidas = consultas.listar_pendencias(con, consultas.FiltroPendencias(regra="total_nota", situacao="resolvidas"))
    assert len(resolvidas) == 1


def test_ibscbs_respeita_configuracao(base):
    con, *_ = base
    cfg = ConfigRegras(ibscbs_ativo=False)
    recalcular_pendencias(con, cfg)
    assert con.execute("SELECT COUNT(*) FROM pendencias WHERE regra='ibscbs'").fetchone()[0] == 0


def test_tabela_ncm(base, tmp_path):
    con, *_ = base
    tabela = tmp_path / "ncm.csv"
    tabela.write_text("Codigo;Descricao\n1006.30.21;Arroz\n0713.33.99;Feijao\n", encoding="utf-8")
    recalcular_pendencias(con, ConfigRegras(tabela_ncm=str(tabela)))
    titulos = [r[0] for r in con.execute("SELECT titulo FROM pendencias WHERE regra='ncm'")]
    assert any("não consta na tabela" in t for t in titulos)


def test_kpis_e_resumo(base):
    con, *_ = base
    k = consultas.kpis(con, "2026-10")
    assert k.clientes == 3
    assert k.faturamento > 0 and k.compras > 0
    assert k.pendencias_alta >= 3
    resumo = consultas.resumo_clientes(con, "2026-10")
    assert resumo[0]["pend_alta"] >= resumo[-1]["pend_alta"]
    assert consultas.periodos(con)[:2] == ["2026-10", "2026-09"]


def test_conferencia_sefaz(base):
    con, g, _, tmp = base
    leitura = sefaz.ler_arquivo_sefaz(tmp / "demo" / "sefaz_padaria_outubro.csv")
    assert len(leitura.registros) == 37
    res = sefaz.conferir(con, PADARIA.cnpj, "2026-10", leitura)
    assert len(res.faltando_no_escritorio) == g.sefaz["faltando_no_escritorio"]
    assert len(res.fora_da_sefaz) == g.sefaz["fora_da_sefaz"]
    assert len(res.cancelada_na_sefaz) == g.sefaz["cancelada_na_sefaz"]
    assert len(res.cancelada_no_escritorio) == g.sefaz["cancelada_no_escritorio"]
    assert res.faltando_no_escritorio[0].numero == 1015
    assert res.fora_da_sefaz[0].numero == 1038
    assert res.cancelada_na_sefaz[0].numero == 1035


def test_sefaz_xlsx_e_chave_com_espacos(base, tmp_path):
    from openpyxl import Workbook
    con, g, *_ = base
    wb = Workbook()
    ws = wb.active
    ws.append(["Chave", "Situação"])
    chave = g.chaves["padaria_1035"]
    ws.append([" ".join(chave[i:i + 4] for i in range(0, 44, 4)), "Cancelada"])
    arq = tmp_path / "sefaz.xlsx"
    wb.save(arq)
    leitura = sefaz.ler_arquivo_sefaz(arq)
    assert [(r.chave, r.situacao) for r in leitura.registros] == [(chave, "cancelada")]


def test_exportacoes(base):
    con, _, _, tmp = base
    xlsx = exportar_relatorio(con, tmp / "rel.xlsx", cnpj=DISTRIBUIDORA.cnpj, ano_mes="2026-10", nome_cliente="Dist")
    wb = load_workbook(xlsx, read_only=True)
    assert {"Resumo", "Notas", "Itens", "Pendências", "Por CFOP", "Por NCM", "Por mês"} <= set(wb.sheetnames)
    assert wb["Notas"].max_row == 1 + 19
    geral = exportar_relatorio(con, tmp / "geral.xlsx")
    assert geral.exists()
    pdf = exportar_pendencias(con, tmp / "pend.pdf", consultas.FiltroPendencias(ano_mes="2026-10"))
    assert pdf.read_bytes()[:4] == b"%PDF"
    leitura = sefaz.ler_arquivo_sefaz(tmp / "demo" / "sefaz_padaria_outubro.csv")
    res = sefaz.conferir(con, PADARIA.cnpj, "2026-10", leitura)
    conf = exportar_conferencia(res, tmp / "conf.xlsx", "Padaria")
    assert "Faltando no escritório" in load_workbook(conf, read_only=True).sheetnames


def test_backup_e_restauracao(base):
    con, g, _, tmp = base
    con.close()
    caminho = tmp / "conferi.db"
    pasta = tmp / "backups"
    for _ in range(3):
        backup.fazer_backup(caminho, pasta, manter=2)
    assert len(backup.listar_backups(pasta)) <= 2
    assert backup.verificar_integridade(caminho)[0]

    # corrompe a base e restaura
    caminho.write_bytes(b"lixo" * 1000)
    for extra in ("-wal", "-shm"):
        Path(str(caminho) + extra).unlink(missing_ok=True)
    assert not backup.verificar_integridade(caminho)[0]
    info = backup.restaurar_mais_recente_valido(pasta, caminho)
    assert info is not None
    assert backup.verificar_integridade(caminho)[0]
    nova = sqlite3.connect(caminho)
    assert nova.execute("SELECT COUNT(*) FROM notas").fetchone()[0] == g.notas_unicas
    nova.close()
    # a base com problema foi preservada
    assert list(tmp.glob("conferi_anterior_*.db"))


def test_backup_corrompido_e_recusado(tmp_path):
    ruim = tmp_path / "conferi_backup_2026-01-01_000000.db.gz"
    ruim.write_bytes(gzip.compress(b"nao e sqlite"))
    ok, _ = backup.testar_backup(ruim)
    assert not ok
    with pytest.raises(ValueError):
        backup.restaurar(ruim, tmp_path / "x.db")
