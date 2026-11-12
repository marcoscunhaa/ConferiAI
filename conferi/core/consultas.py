"""Consultas usadas pelas telas e pelas exportações."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

ORDEM_NIVEL = "CASE p.nivel WHEN 'alta' THEN 0 WHEN 'media' THEN 1 WHEN 'baixa' THEN 2 ELSE 3 END"
NOME_EMPRESA = "COALESCE(NULLIF(e.apelido,''), NULLIF(e.nome_fantasia,''), NULLIF(e.razao_social,''), e.cnpj)"


def tem_clientes(con: sqlite3.Connection) -> bool:
    return con.execute("SELECT 1 FROM empresas WHERE is_cliente = 1 LIMIT 1").fetchone() is not None


def _filtro_clientes(alias: str = "n") -> str:
    return (f"({alias}.emit_doc IN (SELECT cnpj FROM empresas WHERE is_cliente = 1) "
            f"OR {alias}.dest_doc IN (SELECT cnpj FROM empresas WHERE is_cliente = 1))")


def periodos(con: sqlite3.Connection) -> list[str]:
    return [r[0] for r in con.execute(
        "SELECT DISTINCT ano_mes FROM notas WHERE tp_amb = 1 ORDER BY ano_mes DESC")]


def rotulo_periodo(ano_mes: str | None) -> str:
    if not ano_mes:
        return "Todos os períodos"
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
             "outubro", "novembro", "dezembro"]
    ano, mes = ano_mes.split("-")
    return f"{meses[int(mes) - 1].capitalize()} de {ano}"


def lista_clientes(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        f"SELECT e.*, {NOME_EMPRESA} AS nome FROM empresas e WHERE e.is_cliente = 1 ORDER BY nome"
    ).fetchall()


# ----------------------------------------------------------------- painel

@dataclass
class Kpis:
    clientes: int = 0
    notas: int = 0
    faturamento: int = 0
    compras: int = 0
    canceladas: int = 0
    pendencias_alta: int = 0
    pendencias_media: int = 0
    pendencias_baixa: int = 0
    clientes_com_pendencia: int = 0

    @property
    def pendencias_abertas(self) -> int:
        return self.pendencias_alta + self.pendencias_media + self.pendencias_baixa


def kpis(con: sqlite3.Connection, ano_mes: str | None = None) -> Kpis:
    k = Kpis()
    k.clientes = con.execute("SELECT COUNT(*) FROM empresas WHERE is_cliente = 1").fetchone()[0]
    filtro_periodo = "AND n.ano_mes = :am" if ano_mes else ""
    filtro_cli = _filtro_clientes() if k.clientes else "1=1"
    r = con.execute(
        f"""SELECT COUNT(*) AS notas,
                   SUM(CASE WHEN n.cancelada = 1 THEN 1 ELSE 0 END) AS canceladas
            FROM notas n WHERE n.tp_amb = 1 AND {filtro_cli} {filtro_periodo}""",
        {"am": ano_mes},
    ).fetchone()
    k.notas, k.canceladas = r["notas"] or 0, r["canceladas"] or 0
    if k.clientes:
        k.faturamento = con.execute(
            f"""SELECT COALESCE(SUM(n.v_nf),0) FROM notas n
                WHERE n.tp_amb = 1 AND n.cancelada = 0 AND n.tp_nf = 1 AND n.fin_nfe <> 4
                AND n.emit_doc IN (SELECT cnpj FROM empresas WHERE is_cliente = 1) {filtro_periodo}""",
            {"am": ano_mes},
        ).fetchone()[0]
        k.compras = con.execute(
            f"""SELECT COALESCE(SUM(n.v_nf),0) FROM notas n
                WHERE n.tp_amb = 1 AND n.cancelada = 0 AND n.tp_nf = 1
                AND n.dest_doc IN (SELECT cnpj FROM empresas WHERE is_cliente = 1) {filtro_periodo}""",
            {"am": ano_mes},
        ).fetchone()[0]
    filtro_p = "AND p.ano_mes = :am" if ano_mes else ""
    for r in con.execute(
        f"""SELECT p.nivel, COUNT(*) AS qtd, COUNT(DISTINCT p.cnpj_empresa) AS empresas FROM pendencias p
            LEFT JOIN pendencias_situacao s ON s.hash = p.hash
            WHERE s.hash IS NULL AND p.nivel <> 'info' {filtro_p} GROUP BY p.nivel""",
        {"am": ano_mes},
    ):
        setattr(k, f"pendencias_{r['nivel']}", r["qtd"])
    k.clientes_com_pendencia = con.execute(
        f"""SELECT COUNT(DISTINCT p.cnpj_empresa) FROM pendencias p
            LEFT JOIN pendencias_situacao s ON s.hash = p.hash
            WHERE s.hash IS NULL AND p.nivel IN ('alta','media') {filtro_p}""",
        {"am": ano_mes},
    ).fetchone()[0]
    return k


def resumo_clientes(con: sqlite3.Connection, ano_mes: str | None = None) -> list[dict]:
    filtro = "AND n.ano_mes = :am" if ano_mes else ""
    filtro_p = "AND p.ano_mes = :am" if ano_mes else ""
    linhas = con.execute(
        f"""
        SELECT e.cnpj, {NOME_EMPRESA} AS nome, e.regime, e.crt, e.uf,
          (SELECT COUNT(*) FROM notas n WHERE n.emit_doc = e.cnpj AND n.tp_amb = 1 {filtro}) AS notas_saida,
          (SELECT COUNT(*) FROM notas n WHERE n.dest_doc = e.cnpj AND n.tp_amb = 1 {filtro}) AS notas_entrada,
          (SELECT COALESCE(SUM(n.v_nf),0) FROM notas n WHERE n.emit_doc = e.cnpj AND n.tp_amb = 1
              AND n.cancelada = 0 AND n.tp_nf = 1 AND n.fin_nfe <> 4 {filtro}) AS faturamento,
          (SELECT COALESCE(SUM(n.v_nf),0) FROM notas n WHERE n.dest_doc = e.cnpj AND n.tp_amb = 1
              AND n.cancelada = 0 AND n.tp_nf = 1 {filtro}) AS compras,
          (SELECT COUNT(*) FROM notas n WHERE (n.emit_doc = e.cnpj OR n.dest_doc = e.cnpj)
              AND n.cancelada = 1 {filtro}) AS canceladas,
          (SELECT MAX(n.data_emissao) FROM notas n WHERE n.emit_doc = e.cnpj OR n.dest_doc = e.cnpj) AS ultima_nota
        FROM empresas e WHERE e.is_cliente = 1 ORDER BY nome
        """,
        {"am": ano_mes},
    ).fetchall()
    pend = {}
    for r in con.execute(
        f"""SELECT p.cnpj_empresa, p.nivel, COUNT(*) AS qtd FROM pendencias p
            LEFT JOIN pendencias_situacao s ON s.hash = p.hash
            WHERE s.hash IS NULL AND p.nivel <> 'info' {filtro_p}
            GROUP BY p.cnpj_empresa, p.nivel""",
        {"am": ano_mes},
    ):
        pend.setdefault(r["cnpj_empresa"], {})[r["nivel"]] = r["qtd"]
    resultado = []
    for r in linhas:
        d = dict(r)
        niveis = pend.get(r["cnpj"], {})
        d["pend_alta"] = niveis.get("alta", 0)
        d["pend_media"] = niveis.get("media", 0)
        d["pend_baixa"] = niveis.get("baixa", 0)
        resultado.append(d)
    # Prioridade: mais pendências altas primeiro, depois médias, depois faturamento.
    resultado.sort(key=lambda d: (-d["pend_alta"], -d["pend_media"], -d["faturamento"]))
    return resultado


def ultimas_importacoes(con: sqlite3.Connection, limite: int = 5) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM importacoes WHERE finalizado_em IS NOT NULL ORDER BY id DESC LIMIT ?", (limite,)
    ).fetchall()


def rejeitados(con: sqlite3.Connection, importacao_id: int) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT arquivo, motivo, tipo FROM arquivos_rejeitados WHERE importacao_id = ? ORDER BY tipo, arquivo",
        (importacao_id,),
    ).fetchall()


# ----------------------------------------------------------------- notas

@dataclass
class FiltroNotas:
    cnpj: str | None = None
    ano_mes: str | None = None
    papel: str | None = None        # 'saidas' (cliente emitente) | 'entradas' (cliente destinatário)
    modelo: str | None = None       # '55' | '65'
    situacao: str | None = None     # 'ativas' | 'canceladas'
    busca: str = ""
    limite: int = 20000


def listar_notas(con: sqlite3.Connection, f: FiltroNotas) -> list[sqlite3.Row]:
    where, params = ["n.tp_amb IN (1,2)"], {}
    if f.cnpj:
        params["cnpj"] = f.cnpj
        if f.papel == "saidas":
            where.append("n.emit_doc = :cnpj")
        elif f.papel == "entradas":
            where.append("n.dest_doc = :cnpj")
        else:
            where.append("(n.emit_doc = :cnpj OR n.dest_doc = :cnpj)")
    else:
        if tem_clientes(con):
            if f.papel == "saidas":
                where.append("n.emit_doc IN (SELECT cnpj FROM empresas WHERE is_cliente = 1)")
            elif f.papel == "entradas":
                where.append("n.dest_doc IN (SELECT cnpj FROM empresas WHERE is_cliente = 1)")
            else:
                where.append(_filtro_clientes())
    if f.ano_mes:
        where.append("n.ano_mes = :am")
        params["am"] = f.ano_mes
    if f.modelo:
        where.append("n.modelo = :modelo")
        params["modelo"] = f.modelo
    if f.situacao == "ativas":
        where.append("n.cancelada = 0")
    elif f.situacao == "canceladas":
        where.append("n.cancelada = 1")
    if f.busca.strip():
        params["busca"] = f"%{f.busca.strip()}%"
        where.append("(CAST(n.numero AS TEXT) LIKE :busca OR n.chave LIKE :busca OR n.emit_nome LIKE :busca "
                     "OR n.dest_nome LIKE :busca OR n.emit_doc LIKE :busca OR n.dest_doc LIKE :busca)")
    params["limite"] = f.limite
    return con.execute(
        f"""SELECT n.*,
              (SELECT COUNT(*) FROM pendencias p LEFT JOIN pendencias_situacao s ON s.hash = p.hash
               WHERE p.chave = n.chave AND s.hash IS NULL AND p.nivel IN ('alta','media')) AS pendencias
            FROM notas n WHERE {' AND '.join(where)}
            ORDER BY n.data_emissao DESC, n.numero DESC LIMIT :limite""",
        params,
    ).fetchall()


def detalhes_nota(con: sqlite3.Connection, chave: str) -> dict:
    return {
        "nota": con.execute("SELECT * FROM notas WHERE chave = ?", (chave,)).fetchone(),
        "itens": con.execute("SELECT * FROM itens WHERE chave = ? ORDER BY n_item", (chave,)).fetchall(),
        "pagamentos": con.execute("SELECT * FROM pagamentos WHERE chave = ? ORDER BY ordem", (chave,)).fetchall(),
        "eventos": con.execute("SELECT * FROM eventos WHERE chave = ? ORDER BY dh_evento", (chave,)).fetchall(),
        "pendencias": con.execute(
            f"""SELECT p.*, COALESCE(s.situacao,'aberta') AS situacao FROM pendencias p
                LEFT JOIN pendencias_situacao s ON s.hash = p.hash
                WHERE p.chave = ? ORDER BY {ORDEM_NIVEL}""", (chave,)).fetchall(),
    }


# ----------------------------------------------------------------- pendências

@dataclass
class FiltroPendencias:
    cnpj: str | None = None
    ano_mes: str | None = None
    nivel: str | None = None
    regra: str | None = None
    situacao: str = "abertas"       # abertas | resolvidas | ignoradas | todas
    incluir_info: bool = False
    busca: str = ""


def listar_pendencias(con: sqlite3.Connection, f: FiltroPendencias) -> list[sqlite3.Row]:
    where, params = [], {}
    if f.cnpj:
        where.append("p.cnpj_empresa = :cnpj")
        params["cnpj"] = f.cnpj
    if f.ano_mes:
        where.append("p.ano_mes = :am")
        params["am"] = f.ano_mes
    if f.nivel:
        where.append("p.nivel = :nivel")
        params["nivel"] = f.nivel
    elif not f.incluir_info:
        where.append("p.nivel <> 'info'")
    if f.regra:
        where.append("p.regra = :regra")
        params["regra"] = f.regra
    if f.situacao == "abertas":
        where.append("s.hash IS NULL")
    elif f.situacao == "resolvidas":
        where.append("s.situacao = 'resolvida'")
    elif f.situacao == "ignoradas":
        where.append("s.situacao = 'ignorada'")
    if f.busca.strip():
        params["busca"] = f"%{f.busca.strip()}%"
        where.append("(p.titulo LIKE :busca OR p.detalhe LIKE :busca OR CAST(p.numero AS TEXT) LIKE :busca "
                     "OR e.razao_social LIKE :busca)")
    clausula = ("WHERE " + " AND ".join(where)) if where else ""
    return con.execute(
        f"""SELECT p.*, COALESCE(s.situacao,'aberta') AS situacao, {NOME_EMPRESA} AS empresa_nome
            FROM pendencias p
            LEFT JOIN pendencias_situacao s ON s.hash = p.hash
            LEFT JOIN empresas e ON e.cnpj = p.cnpj_empresa
            {clausula}
            ORDER BY {ORDEM_NIVEL}, empresa_nome, p.data_ref, p.numero""",
        params,
    ).fetchall()


def contagem_por_regra(con: sqlite3.Connection, ano_mes: str | None = None) -> list[sqlite3.Row]:
    filtro = "AND p.ano_mes = :am" if ano_mes else ""
    return con.execute(
        f"""SELECT p.regra, COUNT(*) AS qtd FROM pendencias p LEFT JOIN pendencias_situacao s ON s.hash = p.hash
            WHERE s.hash IS NULL AND p.nivel <> 'info' {filtro} GROUP BY p.regra ORDER BY qtd DESC""",
        {"am": ano_mes},
    ).fetchall()
