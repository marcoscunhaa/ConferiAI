"""Identificação de quais empresas são clientes do escritório.

Toda nota tem dois CNPJs. O sistema sugere quem é cliente com base na frequência e no
papel de cada CNPJ; o usuário confirma uma única vez.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

REGIMES = ["", "MEI", "Simples Nacional", "Lucro Presumido", "Lucro Real"]

CRT_DESCRICAO = {
    "1": "Simples Nacional",
    "2": "Simples Nacional (excesso de sublimite)",
    "3": "Regime normal",
    "4": "MEI",
}


def regime_sugerido(crt: str) -> str:
    return {"1": "Simples Nacional", "2": "Simples Nacional", "4": "MEI"}.get(crt, "")


@dataclass
class SugestaoCliente:
    cnpj: str
    nome: str
    uf: str
    crt: str
    como_emitente: int
    como_destinatario: int
    nfce_emitidas: int
    is_cliente: int | None
    sugerido: bool
    motivo: str
    regime: str

    @property
    def total(self) -> int:
        return self.como_emitente + self.como_destinatario


def sugerir_clientes(con: sqlite3.Connection) -> list[SugestaoCliente]:
    total_notas = con.execute("SELECT COUNT(*) FROM notas").fetchone()[0] or 1
    linhas = con.execute(
        """
        SELECT e.cnpj, e.razao_social, e.uf, e.crt, e.is_cliente, e.regime,
               (SELECT COUNT(*) FROM notas n WHERE n.emit_doc = e.cnpj) AS emit,
               (SELECT COUNT(*) FROM notas n WHERE n.dest_doc = e.cnpj) AS dest,
               (SELECT COUNT(*) FROM notas n WHERE n.emit_doc = e.cnpj AND n.modelo = '65') AS nfce,
               (SELECT COUNT(DISTINCT n.emit_doc) FROM notas n WHERE n.dest_doc = e.cnpj) AS fornecedores
        FROM empresas e
        """
    ).fetchall()

    sugestoes = []
    for r in linhas:
        emit, dest, nfce = r["emit"], r["dest"], r["nfce"]
        participacao = emit / total_notas
        if nfce > 0:
            sugerido, motivo = True, "emite NFC-e"
        elif emit > 0 and dest > 0:
            sugerido, motivo = True, "aparece como emitente e destinatário"
        elif participacao >= 0.15:
            sugerido, motivo = True, f"emitiu {participacao:.0%} das notas"
        elif r["fornecedores"] >= 3:
            sugerido, motivo = True, f"recebe notas de {r['fornecedores']} fornecedores"
        elif dest > 0 and emit == 0:
            sugerido, motivo = False, "só aparece como comprador (provável cliente de um cliente)"
        else:
            sugerido, motivo = False, "aparece poucas vezes (provável fornecedor ou comprador)"
        sugestoes.append(SugestaoCliente(
            cnpj=r["cnpj"], nome=r["razao_social"], uf=r["uf"], crt=r["crt"],
            como_emitente=emit, como_destinatario=dest, nfce_emitidas=nfce,
            is_cliente=r["is_cliente"], sugerido=sugerido, motivo=motivo,
            regime=r["regime"] or regime_sugerido(r["crt"]),
        ))
    sugestoes.sort(key=lambda s: (not s.sugerido, -s.total))
    return sugestoes


def existem_pendentes_de_confirmacao(con: sqlite3.Connection) -> bool:
    return con.execute("SELECT 1 FROM empresas WHERE is_cliente IS NULL LIMIT 1").fetchone() is not None


def salvar_clientes(con: sqlite3.Connection, decisoes: dict[str, tuple[bool, str]]) -> None:
    """decisoes: cnpj -> (é cliente?, regime)."""
    con.executemany(
        "UPDATE empresas SET is_cliente = ?, regime = ? WHERE cnpj = ?",
        [(int(ok), regime, cnpj) for cnpj, (ok, regime) in decisoes.items()],
    )
    con.commit()


def confirmar_sugestoes_automaticamente(con: sqlite3.Connection) -> None:
    """Usado quando o usuário fecha a janela de confirmação sem decidir."""
    decisoes = {}
    for s in sugerir_clientes(con):
        if s.is_cliente is None:
            decisoes[s.cnpj] = (s.sugerido, s.regime)
    salvar_clientes(con, decisoes)


def clientes_confirmados(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM empresas WHERE is_cliente = 1 ORDER BY COALESCE(NULLIF(apelido,''), razao_social)"
    ).fetchall()


def nome_exibicao(row: sqlite3.Row) -> str:
    return row["apelido"] or row["nome_fantasia"] or row["razao_social"] or row["cnpj"]
