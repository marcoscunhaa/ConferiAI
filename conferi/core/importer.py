"""Importação de documentos para a base local.

- Notas repetidas são reconhecidas pela chave de acesso e ignoradas.
- Uma nota sem protocolo é atualizada se depois chegar a versão autorizada (nfeProc).
- Cancelamentos marcam a nota como cancelada, venha o evento antes ou depois da nota.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from .chave import somente_digitos
from .models import Evento, Inutilizacao, Invalido, NaoSuportado, Nota
from .parser import ler_documentos
from .sources import FonteDocumentos

Progresso = Callable[[int, int, str], None]
Cancelado = Callable[[], bool]

LOTE_COMMIT = 400


@dataclass
class ResultadoImportacao:
    importacao_id: int = 0
    total_arquivos: int = 0
    notas_novas: int = 0
    notas_atualizadas: int = 0
    duplicadas: int = 0
    eventos: int = 0
    eventos_duplicados: int = 0
    inutilizacoes: int = 0
    cancelamentos_aplicados: int = 0
    invalidos: list[tuple[str, str]] = field(default_factory=list)
    ignorados: list[tuple[str, str]] = field(default_factory=list)
    empresas_novas: int = 0
    interrompida: bool = False
    segundos: float = 0.0

    @property
    def total_documentos(self) -> int:
        return self.notas_novas + self.notas_atualizadas + self.duplicadas + self.eventos + self.inutilizacoes


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _cfop_principal(nota: Nota) -> str:
    if not nota.itens:
        return ""
    return max(nota.itens, key=lambda i: i.v_prod).cfop


def _registrar_empresa(con: sqlite3.Connection, cnpj: str, nome: str, uf: str, municipio: str,
                       crt: str = "", fantasia: str = "") -> bool:
    """Cria a empresa se ainda não existir. Só CNPJs (14 dígitos) viram empresa."""
    cnpj = somente_digitos(cnpj)
    if len(cnpj) != 14:
        return False
    cur = con.execute(
        "INSERT INTO empresas(cnpj, razao_social, nome_fantasia, uf, municipio, crt) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(cnpj) DO NOTHING",
        (cnpj, nome, fantasia, uf, municipio, crt),
    )
    if cur.rowcount:
        return True
    if crt:
        con.execute("UPDATE empresas SET crt = ? WHERE cnpj = ? AND crt = ''", (crt, cnpj))
    if nome:
        con.execute("UPDATE empresas SET razao_social = ? WHERE cnpj = ? AND razao_social = ''", (nome, cnpj))
    return False


def _inserir_nota(con: sqlite3.Connection, n: Nota, arquivo: str, importacao_id: int) -> None:
    t = n.totais
    cancelada = con.execute(
        "SELECT 1 FROM eventos WHERE chave = ? AND tipo IN ('110111','110112') "
        "AND c_stat IN ('', '135', '136', '155') LIMIT 1",
        (n.chave,),
    ).fetchone() is not None
    con.execute(
        """INSERT INTO notas(chave, versao, modelo, serie, numero, dh_emissao, data_emissao, ano_mes, tp_nf,
           id_dest, fin_nfe, tp_amb, nat_op, emit_doc, emit_nome, emit_uf, emit_crt, dest_doc, dest_nome,
           dest_uf, v_prod, v_desc, v_icms_deson, v_st, v_fcp_st, v_frete, v_seg, v_outro, v_ii, v_ipi,
           v_ipi_devol, v_serv, v_icms, v_pis, v_cofins, v_nf, tem_ibscbs_total, cfop_principal, c_stat,
           n_prot, cancelada, arquivo_origem, importacao_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            n.chave, n.versao, n.modelo, n.serie, n.numero, n.dh_emissao, n.data_emissao, n.data_emissao[:7],
            n.tp_nf, n.id_dest, n.fin_nfe, n.tp_amb, n.nat_op, n.emit_doc, n.emit_nome, n.emit_uf, n.emit_crt,
            n.dest_doc, n.dest_nome, n.dest_uf, t.get("vProd", 0), t.get("vDesc", 0), t.get("vICMSDeson", 0),
            t.get("vST", 0), t.get("vFCPST", 0), t.get("vFrete", 0), t.get("vSeg", 0), t.get("vOutro", 0),
            t.get("vII", 0), t.get("vIPI", 0), t.get("vIPIDevol", 0), t.get("vServ", 0), t.get("vICMS", 0),
            t.get("vPIS", 0), t.get("vCOFINS", 0), t.get("vNF", 0), int(n.tem_ibscbs_total),
            _cfop_principal(n), n.c_stat, n.n_prot, int(cancelada), arquivo, importacao_id,
        ),
    )
    con.executemany(
        """INSERT INTO itens(chave, n_item, codigo, descricao, ncm, cfop, unidade, quantidade, valor_unitario,
           v_prod, v_desc, v_frete, v_seg, v_outro, ind_tot, ibscbs_presente, cst_ibscbs, cclasstrib)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(chave, n_item) DO NOTHING""",
        [
            (n.chave, i.n_item, i.codigo, i.descricao, i.ncm, i.cfop, i.unidade, i.quantidade, i.valor_unitario,
             i.v_prod, i.v_desc, i.v_frete, i.v_seg, i.v_outro, i.ind_tot, int(i.ibscbs_presente), i.cst_ibscbs,
             i.cclasstrib)
            for i in n.itens
        ],
    )
    con.executemany(
        "INSERT INTO pagamentos(chave, ordem, t_pag, valor, tp_integra, cnpj_credenciadora, c_aut) "
        "VALUES (?,?,?,?,?,?,?)",
        [(n.chave, k, p.t_pag, p.valor, p.tp_integra, p.cnpj_credenciadora, p.c_aut)
         for k, p in enumerate(n.pagamentos, start=1)],
    )


def importar(con: sqlite3.Connection, fonte: FonteDocumentos,
             progresso: Progresso | None = None, cancelado: Cancelado | None = None) -> ResultadoImportacao:
    inicio = time.monotonic()
    res = ResultadoImportacao()
    res.total_arquivos = fonte.contar()

    cur = con.execute(
        "INSERT INTO importacoes(iniciado_em, origem, total_arquivos) VALUES (?,?,?)",
        (_agora(), fonte.descricao, res.total_arquivos),
    )
    res.importacao_id = cur.lastrowid
    con.commit()

    processados = 0
    for arquivo in fonte.arquivos():
        if cancelado and cancelado():
            res.interrompida = True
            break
        processados += 1
        if progresso and (processados % 25 == 0 or processados == res.total_arquivos):
            progresso(processados, res.total_arquivos, arquivo.nome)

        if arquivo.erro:
            res.invalidos.append((arquivo.nome, arquivo.erro))
            continue
        try:
            dados = arquivo.ler()
        except OSError as erro:
            res.invalidos.append((arquivo.nome, f"não foi possível ler o arquivo ({erro})"))
            continue

        for doc in ler_documentos(dados):
            if isinstance(doc, Nota):
                _processar_nota(con, doc, arquivo.nome, res)
            elif isinstance(doc, Evento):
                _processar_evento(con, doc, arquivo.nome, res)
            elif isinstance(doc, Inutilizacao):
                cur = con.execute(
                    "INSERT INTO inutilizacoes(cnpj, modelo, serie, n_ini, n_fin, ano, protocolo, c_stat, "
                    "justificativa, arquivo_origem) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                    (somente_digitos(doc.cnpj), doc.modelo, doc.serie, doc.n_ini, doc.n_fin, doc.ano,
                     doc.protocolo, doc.c_stat, doc.justificativa, arquivo.nome),
                )
                res.inutilizacoes += cur.rowcount
            elif isinstance(doc, Invalido):
                res.invalidos.append((arquivo.nome, doc.motivo))
            elif isinstance(doc, NaoSuportado):
                res.ignorados.append((arquivo.nome, doc.motivo))

        if processados % LOTE_COMMIT == 0:
            con.commit()

    if progresso:
        progresso(processados, res.total_arquivos, "")

    con.executemany(
        "INSERT INTO arquivos_rejeitados(importacao_id, arquivo, motivo, tipo) VALUES (?,?,?,?)",
        [(res.importacao_id, a, m, "invalido") for a, m in res.invalidos]
        + [(res.importacao_id, a, m, "ignorado") for a, m in res.ignorados],
    )
    res.segundos = time.monotonic() - inicio
    con.execute(
        """UPDATE importacoes SET finalizado_em=?, notas_novas=?, notas_atualizadas=?, duplicadas=?, eventos=?,
           inutilizacoes=?, invalidos=?, ignorados=? WHERE id=?""",
        (_agora(), res.notas_novas, res.notas_atualizadas, res.duplicadas, res.eventos, res.inutilizacoes,
         len(res.invalidos), len(res.ignorados), res.importacao_id),
    )
    con.commit()
    return res


def _processar_nota(con: sqlite3.Connection, nota: Nota, arquivo: str, res: ResultadoImportacao) -> None:
    existente = con.execute("SELECT n_prot FROM notas WHERE chave = ?", (nota.chave,)).fetchone()
    if existente is not None:
        if not existente["n_prot"] and nota.n_prot:
            con.execute(
                "UPDATE notas SET c_stat=?, n_prot=?, arquivo_origem=? WHERE chave=?",
                (nota.c_stat, nota.n_prot, arquivo, nota.chave),
            )
            res.notas_atualizadas += 1
        else:
            res.duplicadas += 1
        return

    res.empresas_novas += _registrar_empresa(con, nota.emit_doc, nota.emit_nome, nota.emit_uf,
                                             nota.emit_municipio, nota.emit_crt, nota.emit_fantasia)
    res.empresas_novas += _registrar_empresa(con, nota.dest_doc, nota.dest_nome, nota.dest_uf, nota.dest_municipio)
    _inserir_nota(con, nota, arquivo, res.importacao_id)
    res.notas_novas += 1


def _processar_evento(con: sqlite3.Connection, ev: Evento, arquivo: str, res: ResultadoImportacao) -> None:
    cur = con.execute(
        """INSERT INTO eventos(chave, tipo, sequencia, dh_evento, descricao, justificativa, c_stat, protocolo,
           arquivo_origem) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING""",
        (ev.chave, ev.tipo, ev.sequencia, ev.dh_evento, ev.descricao, ev.justificativa, ev.c_stat,
         ev.protocolo, arquivo),
    )
    if not cur.rowcount:
        res.eventos_duplicados += 1
        res.duplicadas += 1
        return
    res.eventos += 1
    if ev.e_cancelamento and ev.registrado:
        upd = con.execute("UPDATE notas SET cancelada = 1 WHERE chave = ? AND cancelada = 0", (ev.chave,))
        res.cancelamentos_aplicados += upd.rowcount
