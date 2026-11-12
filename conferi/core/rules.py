"""Regras de conferência.

As regras são determinísticas: o mesmo conjunto de notas gera sempre as mesmas pendências.
Cada pendência aponta a nota, o motivo e um nível. São alertas para conferência do
profissional responsável, não um diagnóstico fiscal.

As regras do IBS/CBS seguem parâmetros configuráveis, porque a transição da reforma
tributária ainda está em ajuste. Confirme as regras nas notas técnicas vigentes.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .chave import somente_digitos
from .config import ConfigRegras
from .money import fmt_brl

NIVEIS = ("alta", "media", "baixa", "info")
NIVEL_ROTULO = {"alta": "Alta", "media": "Média", "baixa": "Baixa", "info": "Informativo"}

REGRAS = {
    "sequencia": "Lacuna na numeração",
    "soma_itens": "Soma dos itens",
    "total_nota": "Total da nota",
    "cfop_operacao": "CFOP × tipo de operação",
    "cfop_destino": "CFOP × destino",
    "uf_destino": "UF × destino",
    "cfop_devolucao": "CFOP em devolução",
    "ncm": "NCM",
    "ibscbs": "IBS/CBS",
    "protocolo": "Autorização",
    "homologacao": "Ambiente de teste",
    "cancelada": "Cancelada",
}

CSTAT_DENEGADA = {"110", "301", "302", "303"}
CFOP_DIGITO_OPERACAO = {0: {"1", "2", "3"}, 1: {"5", "6", "7"}}
CFOP_DIGITO_DESTINO = {1: {"1", "5"}, 2: {"2", "6"}, 3: {"3", "7"}}
# Vendas de mercadoria (x101–x125) e vendas com ST (x401–x405).
CFOP_VENDA = {f"{x}{n:03d}" for x in "56" for n in list(range(101, 126)) + list(range(401, 406))}


@dataclass
class Pendencia:
    regra: str
    nivel: str
    titulo: str
    detalhe: str = ""
    cnpj_empresa: str = ""
    chave: str = ""
    modelo: str = ""
    serie: int | None = None
    numero: int | None = None
    data_ref: str = ""
    n_item: int | None = None
    identificador: str = ""   # usado no hash quando não há chave (ex.: lacunas)

    @property
    def hash(self) -> str:
        base = f"{self.regra}|{self.chave or self.cnpj_empresa}|{self.identificador}|{self.n_item or ''}"
        return hashlib.sha1(base.encode()).hexdigest()


# ----------------------------------------------------------------- tabela NCM

def carregar_tabela_ncm(caminho: str) -> set[str] | None:
    """Aceita o JSON da tabela vigente (Siscomex) ou um CSV/TXT com o código na primeira coluna."""
    if not caminho:
        return None
    arquivo = Path(caminho)
    if not arquivo.exists():
        return None
    texto = arquivo.read_text(encoding="utf-8", errors="ignore")
    codigos: set[str] = set()
    if arquivo.suffix.lower() == ".json":
        try:
            dados = json.loads(texto)
        except json.JSONDecodeError:
            return None
        itens = dados.get("Nomenclaturas", dados) if isinstance(dados, dict) else dados
        for item in itens:
            codigo = somente_digitos(str(item.get("Codigo", ""))) if isinstance(item, dict) else ""
            if len(codigo) == 8:
                codigos.add(codigo)
    else:
        for linha in texto.splitlines():
            primeira = linha.replace(",", ";").split(";")[0]
            codigo = somente_digitos(primeira)
            if len(codigo) == 8:
                codigos.add(codigo)
    return codigos or None


# ----------------------------------------------------------------- execução

class MotorRegras:
    def __init__(self, cfg: ConfigRegras, tabela_ncm: set[str] | None = None):
        self.cfg = cfg
        self.tabela_ncm = tabela_ncm

    def executar(self, con: sqlite3.Connection) -> int:
        """Recalcula todas as pendências e grava no banco. Retorna a quantidade."""
        clientes = {r[0] for r in con.execute("SELECT cnpj FROM empresas WHERE is_cliente = 1")}
        todos = not clientes  # sem clientes confirmados, confere tudo pelo emitente

        pendencias: list[Pendencia] = []
        itens_por_nota: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for item in con.execute("SELECT * FROM itens ORDER BY chave, n_item"):
            itens_por_nota[item["chave"]].append(item)

        for nota in con.execute("SELECT * FROM notas"):
            if nota["emit_doc"] in clientes or todos:
                empresa, propria = nota["emit_doc"], True
            elif nota["dest_doc"] in clientes:
                empresa, propria = nota["dest_doc"], False
            else:
                continue
            pendencias.extend(self._regras_da_nota(nota, itens_por_nota.get(nota["chave"], []), empresa, propria))

        pendencias.extend(self._lacunas(con, clientes, todos))
        self._gravar(con, pendencias)
        return len(pendencias)

    # ------------------------------------------------------------- por nota
    def _base(self, nota: sqlite3.Row, empresa: str, regra: str, nivel: str, titulo: str,
              detalhe: str = "", identificador: str = "", n_item: int | None = None) -> Pendencia:
        return Pendencia(
            regra=regra, nivel=nivel, titulo=titulo, detalhe=detalhe, cnpj_empresa=empresa,
            chave=nota["chave"], modelo=nota["modelo"], serie=nota["serie"], numero=nota["numero"],
            data_ref=nota["data_emissao"], identificador=identificador, n_item=n_item,
        )

    def _regras_da_nota(self, nota: sqlite3.Row, itens: list[sqlite3.Row], empresa: str,
                        propria: bool) -> list[Pendencia]:
        p: list[Pendencia] = []
        add = p.append

        if nota["tp_amb"] == 2:
            add(self._base(nota, empresa, "homologacao", "info", "Nota emitida em ambiente de homologação",
                           "Documento de teste, sem valor fiscal. Não entra nos totais."))
            return p
        if nota["cancelada"]:
            add(self._base(nota, empresa, "cancelada", "info", "Nota cancelada",
                           "Evento de cancelamento encontrado. A nota foi retirada dos totais."))
            return p
        if nota["c_stat"] in CSTAT_DENEGADA:
            add(self._base(nota, empresa, "protocolo", "alta", "Uso denegado pela Sefaz",
                           f"Código de situação {nota['c_stat']}. A nota não tem validade fiscal."))
            return p
        if not nota["n_prot"]:
            add(self._base(nota, empresa, "protocolo", "baixa", "Arquivo sem protocolo de autorização",
                           "O XML recebido não traz o protocolo da Sefaz. Peça a versão autorizada ou "
                           "confirme a situação no portal."))

        tol = self.cfg.tolerancia_total_centavos

        # Soma dos itens × valor dos produtos
        soma = sum(i["v_prod"] for i in itens if i["ind_tot"] == 1)
        if itens and abs(soma - nota["v_prod"]) > tol:
            add(self._base(nota, empresa, "soma_itens", "alta", "Soma dos itens diferente do total de produtos",
                           f"Itens somam {fmt_brl(soma)}; a nota informa {fmt_brl(nota['v_prod'])} "
                           f"(diferença de {fmt_brl(soma - nota['v_prod'])})."))

        # Composição do total da nota
        base = (nota["v_prod"] - nota["v_desc"] + nota["v_st"] + nota["v_fcp_st"] + nota["v_frete"]
                + nota["v_seg"] + nota["v_outro"] + nota["v_ii"] + nota["v_ipi"] + nota["v_ipi_devol"]
                + nota["v_serv"])
        candidatos = (base, base - nota["v_icms_deson"])
        if min(abs(nota["v_nf"] - c) for c in candidatos) > tol:
            add(self._base(nota, empresa, "total_nota", "alta", "Total da nota não fecha com a composição",
                           f"Total informado {fmt_brl(nota['v_nf'])}; produtos, descontos, frete, seguro, "
                           f"outras despesas e impostos somam {fmt_brl(base)} "
                           f"(diferença de {fmt_brl(nota['v_nf'] - base)})."))

        # CFOP
        cfops_operacao, cfops_destino, cfops_devolucao = set(), set(), set()
        for i in itens:
            cfop = i["cfop"]
            if len(cfop) != 4:
                continue
            if cfop[0] not in CFOP_DIGITO_OPERACAO.get(nota["tp_nf"], {cfop[0]}):
                cfops_operacao.add(cfop)
            elif cfop[0] not in CFOP_DIGITO_DESTINO.get(nota["id_dest"], {cfop[0]}):
                cfops_destino.add(cfop)
            if nota["fin_nfe"] == 4 and cfop in CFOP_VENDA:
                cfops_devolucao.add(cfop)
        tipo = "saída" if nota["tp_nf"] == 1 else "entrada"
        for cfop in sorted(cfops_operacao):
            add(self._base(nota, empresa, "cfop_operacao", "alta", f"CFOP {cfop} incompatível com nota de {tipo}",
                           f"CFOPs iniciados por {cfop[0]} não são usados em notas de {tipo}.", identificador=cfop))
        destino = {1: "interna", 2: "interestadual", 3: "com o exterior"}.get(nota["id_dest"], "")
        for cfop in sorted(cfops_destino):
            add(self._base(nota, empresa, "cfop_destino", "media", f"CFOP {cfop} incompatível com operação {destino}",
                           "O primeiro dígito do CFOP não corresponde ao destino informado na nota.",
                           identificador=cfop))
        for cfop in sorted(cfops_devolucao):
            add(self._base(nota, empresa, "cfop_devolucao", "media", f"CFOP de venda ({cfop}) em nota de devolução",
                           "A nota está marcada como devolução, mas usa CFOP de venda.", identificador=cfop))

        # UF do destinatário × indicador de destino (somente NF-e)
        if (nota["modelo"] == "55" and nota["emit_uf"] and nota["dest_uf"] and nota["dest_uf"] != "EX"
                and nota["dest_uf"] != nota["emit_uf"] and nota["id_dest"] == 1):
            add(self._base(nota, empresa, "uf_destino", "media",
                           f"Destinatário em {nota['dest_uf']}, mas a operação está marcada como interna",
                           f"Emitente em {nota['emit_uf']} e destinatário em {nota['dest_uf']}. "
                           "Confira o indicador de destino e o CFOP."))

        # NCM
        ncm_formato, ncm_inexistente = defaultdict(int), defaultdict(int)
        for i in itens:
            ncm = i["ncm"]
            if not (len(ncm) == 8 and ncm.isdigit()):
                ncm_formato[ncm or "(vazio)"] += 1
            elif self.tabela_ncm is not None and ncm != "00000000" and ncm not in self.tabela_ncm:
                ncm_inexistente[ncm] += 1
        for ncm, qtd in sorted(ncm_formato.items()):
            add(self._base(nota, empresa, "ncm", "media", f"NCM com formato inválido: {ncm}",
                           f"{qtd} item(ns). O NCM deve ter 8 dígitos numéricos.", identificador="fmt" + ncm))
        for ncm, qtd in sorted(ncm_inexistente.items()):
            add(self._base(nota, empresa, "ncm", "media", f"NCM {ncm} não consta na tabela vigente",
                           f"{qtd} item(ns). O código pode ter sido extinto ou digitado errado.",
                           identificador="tab" + ncm))

        # IBS/CBS (somente notas emitidas pelo próprio cliente)
        if (propria and self.cfg.ibscbs_ativo and itens and nota["data_emissao"] >= self.cfg.ibscbs_inicio
                and nota["emit_crt"] in set(self.cfg.ibscbs_crts)):
            sem_grupo = [i for i in itens if not i["ibscbs_presente"]]
            vazios = [i for i in itens if i["ibscbs_presente"] and (not i["cst_ibscbs"] or not i["cclasstrib"])]
            formato = [i for i in itens if i["ibscbs_presente"] and i["cst_ibscbs"] and i["cclasstrib"]
                       and not (len(i["cst_ibscbs"]) == 3 and i["cst_ibscbs"].isdigit()
                                and len(i["cclasstrib"]) == 6 and i["cclasstrib"].isdigit())]
            if sem_grupo:
                add(self._base(nota, empresa, "ibscbs", "media",
                               f"Grupo IBS/CBS ausente em {len(sem_grupo)} de {len(itens)} itens",
                               "A nota foi emitida no período de transição sem o grupo de IBS/CBS nesses itens. "
                               "Verifique o cadastro de produtos e o emissor do cliente.", identificador="sem"))
            if vazios:
                add(self._base(nota, empresa, "ibscbs", "media",
                               f"CST ou classificação tributária vazios em {len(vazios)} itens",
                               "O grupo IBS/CBS existe, mas sem CST ou cClassTrib preenchidos.",
                               identificador="vazio"))
            if formato:
                add(self._base(nota, empresa, "ibscbs", "baixa",
                               f"CST ou classificação tributária fora do formato em {len(formato)} itens",
                               "Esperado: CST com 3 dígitos e cClassTrib com 6 dígitos.", identificador="fmt"))
        return p

    # ------------------------------------------------------------- lacunas
    def _lacunas(self, con: sqlite3.Connection, clientes: set[str], todos: bool) -> list[Pendencia]:
        inutilizadas: dict[tuple, list[tuple[int, int]]] = defaultdict(list)
        for r in con.execute("SELECT cnpj, modelo, serie, n_ini, n_fin, c_stat FROM inutilizacoes"):
            if r["c_stat"] in ("", "102"):
                inutilizadas[(r["cnpj"], r["modelo"], r["serie"])].append((r["n_ini"], r["n_fin"]))

        grupos: dict[tuple, list[tuple[int, str]]] = defaultdict(list)
        for r in con.execute(
            "SELECT emit_doc, modelo, serie, numero, data_emissao FROM notas WHERE tp_amb = 1 "
            "ORDER BY emit_doc, modelo, serie, numero"
        ):
            if todos or r["emit_doc"] in clientes:
                grupos[(r["emit_doc"], r["modelo"], r["serie"])].append((r["numero"], r["data_emissao"]))

        pendencias = []
        for (cnpj, modelo, serie), numeros in grupos.items():
            faixas_inut = inutilizadas.get((cnpj, modelo, serie), [])
            for (atual, _), (proximo, data_prox) in zip(numeros, numeros[1:]):
                if proximo - atual <= 1:
                    continue
                for ini, fim in self._subtrair_inutilizadas(atual + 1, proximo - 1, faixas_inut):
                    qtd = fim - ini + 1
                    faixa = f"{ini}" if qtd == 1 else f"{ini} a {fim}"
                    tipo = "NFC-e" if modelo == "65" else "NF-e"
                    pendencias.append(Pendencia(
                        regra="sequencia", nivel="alta",
                        titulo=f"{qtd} número(s) ausente(s) na sequência: {faixa}",
                        detalhe=f"{tipo} série {serie}. Confirme com o cliente se as notas foram emitidas e não "
                                "enviadas, canceladas ou inutilizadas.",
                        cnpj_empresa=cnpj, modelo=modelo, serie=serie, numero=ini, data_ref=data_prox,
                        identificador=f"{modelo}-{serie}-{ini}-{fim}",
                    ))
        return pendencias

    @staticmethod
    def _subtrair_inutilizadas(ini: int, fim: int, faixas: list[tuple[int, int]]) -> list[tuple[int, int]]:
        restantes = [(ini, fim)]
        for a, b in faixas:
            novos = []
            for x, y in restantes:
                if b < x or a > y:
                    novos.append((x, y))
                    continue
                if a > x:
                    novos.append((x, a - 1))
                if b < y:
                    novos.append((b + 1, y))
            restantes = novos
        return restantes

    # ------------------------------------------------------------- gravação
    @staticmethod
    def _gravar(con: sqlite3.Connection, pendencias: list[Pendencia]) -> None:
        vistos = set()
        linhas = []
        for p in pendencias:
            h = p.hash
            if h in vistos:
                continue
            vistos.add(h)
            linhas.append((h, p.regra, p.nivel, p.cnpj_empresa, p.chave, p.modelo, p.serie, p.numero,
                           p.data_ref, p.data_ref[:7], p.titulo, p.detalhe, p.n_item))
        con.execute("DELETE FROM pendencias")
        con.executemany(
            """INSERT INTO pendencias(hash, regra, nivel, cnpj_empresa, chave, modelo, serie, numero, data_ref,
               ano_mes, titulo, detalhe, n_item) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            linhas,
        )
        con.commit()


def recalcular_pendencias(con: sqlite3.Connection, cfg: ConfigRegras) -> int:
    return MotorRegras(cfg, carregar_tabela_ncm(cfg.tabela_ncm)).executar(con)


def definir_situacao(con: sqlite3.Connection, hashes: list[str], situacao: str | None) -> None:
    """situacao: 'resolvida', 'ignorada' ou None para reabrir."""
    if situacao is None:
        con.executemany("DELETE FROM pendencias_situacao WHERE hash = ?", [(h,) for h in hashes])
    else:
        con.executemany(
            "INSERT INTO pendencias_situacao(hash, situacao) VALUES (?, ?) "
            "ON CONFLICT(hash) DO UPDATE SET situacao = excluded.situacao, atualizado_em = datetime('now','localtime')",
            [(h, situacao) for h in hashes],
        )
    con.commit()
