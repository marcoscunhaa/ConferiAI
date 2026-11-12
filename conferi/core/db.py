"""Banco de dados local (SQLite).

Cada thread abre a sua própria conexão com `abrir()`. Valores em dinheiro são inteiros
em centavos. A chave de acesso é o identificador único de cada nota.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

VERSAO_SCHEMA = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS empresas (
    cnpj TEXT PRIMARY KEY,
    razao_social TEXT NOT NULL DEFAULT '',
    nome_fantasia TEXT NOT NULL DEFAULT '',
    uf TEXT NOT NULL DEFAULT '',
    municipio TEXT NOT NULL DEFAULT '',
    crt TEXT NOT NULL DEFAULT '',
    regime TEXT NOT NULL DEFAULT '',          -- definido pelo usuário: Simples, MEI, Presumido, Real
    is_cliente INTEGER,                        -- NULL = ainda não confirmado
    apelido TEXT NOT NULL DEFAULT '',
    observacoes TEXT NOT NULL DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS importacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    iniciado_em TEXT NOT NULL,
    finalizado_em TEXT,
    origem TEXT NOT NULL DEFAULT '',
    total_arquivos INTEGER NOT NULL DEFAULT 0,
    notas_novas INTEGER NOT NULL DEFAULT 0,
    notas_atualizadas INTEGER NOT NULL DEFAULT 0,
    duplicadas INTEGER NOT NULL DEFAULT 0,
    eventos INTEGER NOT NULL DEFAULT 0,
    inutilizacoes INTEGER NOT NULL DEFAULT 0,
    invalidos INTEGER NOT NULL DEFAULT 0,
    ignorados INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS arquivos_rejeitados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    importacao_id INTEGER NOT NULL REFERENCES importacoes(id) ON DELETE CASCADE,
    arquivo TEXT NOT NULL,
    motivo TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'invalido'      -- invalido | ignorado
);

CREATE TABLE IF NOT EXISTS notas (
    chave TEXT PRIMARY KEY,
    versao TEXT NOT NULL DEFAULT '',
    modelo TEXT NOT NULL,
    serie INTEGER NOT NULL,
    numero INTEGER NOT NULL,
    dh_emissao TEXT NOT NULL DEFAULT '',
    data_emissao TEXT NOT NULL,
    ano_mes TEXT NOT NULL,
    tp_nf INTEGER NOT NULL,
    id_dest INTEGER NOT NULL,
    fin_nfe INTEGER NOT NULL,
    tp_amb INTEGER NOT NULL,
    nat_op TEXT NOT NULL DEFAULT '',
    emit_doc TEXT NOT NULL DEFAULT '',
    emit_nome TEXT NOT NULL DEFAULT '',
    emit_uf TEXT NOT NULL DEFAULT '',
    emit_crt TEXT NOT NULL DEFAULT '',
    dest_doc TEXT NOT NULL DEFAULT '',
    dest_nome TEXT NOT NULL DEFAULT '',
    dest_uf TEXT NOT NULL DEFAULT '',
    v_prod INTEGER NOT NULL DEFAULT 0,
    v_desc INTEGER NOT NULL DEFAULT 0,
    v_icms_deson INTEGER NOT NULL DEFAULT 0,
    v_st INTEGER NOT NULL DEFAULT 0,
    v_fcp_st INTEGER NOT NULL DEFAULT 0,
    v_frete INTEGER NOT NULL DEFAULT 0,
    v_seg INTEGER NOT NULL DEFAULT 0,
    v_outro INTEGER NOT NULL DEFAULT 0,
    v_ii INTEGER NOT NULL DEFAULT 0,
    v_ipi INTEGER NOT NULL DEFAULT 0,
    v_ipi_devol INTEGER NOT NULL DEFAULT 0,
    v_serv INTEGER NOT NULL DEFAULT 0,
    v_icms INTEGER NOT NULL DEFAULT 0,
    v_pis INTEGER NOT NULL DEFAULT 0,
    v_cofins INTEGER NOT NULL DEFAULT 0,
    v_nf INTEGER NOT NULL DEFAULT 0,
    tem_ibscbs_total INTEGER NOT NULL DEFAULT 0,
    cfop_principal TEXT NOT NULL DEFAULT '',
    c_stat TEXT NOT NULL DEFAULT '',
    n_prot TEXT NOT NULL DEFAULT '',
    cancelada INTEGER NOT NULL DEFAULT 0,
    arquivo_origem TEXT NOT NULL DEFAULT '',
    importacao_id INTEGER,
    importado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_notas_emit ON notas(emit_doc, ano_mes);
CREATE INDEX IF NOT EXISTS ix_notas_dest ON notas(dest_doc, ano_mes);
CREATE INDEX IF NOT EXISTS ix_notas_seq ON notas(emit_doc, modelo, serie, numero);

CREATE TABLE IF NOT EXISTS itens (
    chave TEXT NOT NULL REFERENCES notas(chave) ON DELETE CASCADE,
    n_item INTEGER NOT NULL,
    codigo TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL DEFAULT '',
    ncm TEXT NOT NULL DEFAULT '',
    cfop TEXT NOT NULL DEFAULT '',
    unidade TEXT NOT NULL DEFAULT '',
    quantidade TEXT NOT NULL DEFAULT '0',
    valor_unitario TEXT NOT NULL DEFAULT '0',
    v_prod INTEGER NOT NULL DEFAULT 0,
    v_desc INTEGER NOT NULL DEFAULT 0,
    v_frete INTEGER NOT NULL DEFAULT 0,
    v_seg INTEGER NOT NULL DEFAULT 0,
    v_outro INTEGER NOT NULL DEFAULT 0,
    ind_tot INTEGER NOT NULL DEFAULT 1,
    ibscbs_presente INTEGER NOT NULL DEFAULT 0,
    cst_ibscbs TEXT NOT NULL DEFAULT '',
    cclasstrib TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (chave, n_item)
);
CREATE INDEX IF NOT EXISTS ix_itens_ncm ON itens(ncm);

CREATE TABLE IF NOT EXISTS pagamentos (
    chave TEXT NOT NULL REFERENCES notas(chave) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    t_pag TEXT NOT NULL DEFAULT '',
    valor INTEGER NOT NULL DEFAULT 0,
    tp_integra TEXT NOT NULL DEFAULT '',
    cnpj_credenciadora TEXT NOT NULL DEFAULT '',
    c_aut TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (chave, ordem)
);

CREATE TABLE IF NOT EXISTS eventos (
    chave TEXT NOT NULL,
    tipo TEXT NOT NULL,
    sequencia INTEGER NOT NULL,
    dh_evento TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL DEFAULT '',
    justificativa TEXT NOT NULL DEFAULT '',
    c_stat TEXT NOT NULL DEFAULT '',
    protocolo TEXT NOT NULL DEFAULT '',
    arquivo_origem TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (chave, tipo, sequencia)
);

CREATE TABLE IF NOT EXISTS inutilizacoes (
    cnpj TEXT NOT NULL,
    modelo TEXT NOT NULL,
    serie INTEGER NOT NULL,
    n_ini INTEGER NOT NULL,
    n_fin INTEGER NOT NULL,
    ano TEXT NOT NULL DEFAULT '',
    protocolo TEXT NOT NULL DEFAULT '',
    c_stat TEXT NOT NULL DEFAULT '',
    justificativa TEXT NOT NULL DEFAULT '',
    arquivo_origem TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (cnpj, modelo, serie, n_ini, n_fin)
);

CREATE TABLE IF NOT EXISTS pendencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT NOT NULL UNIQUE,
    regra TEXT NOT NULL,
    nivel TEXT NOT NULL,
    cnpj_empresa TEXT NOT NULL DEFAULT '',
    chave TEXT NOT NULL DEFAULT '',
    modelo TEXT NOT NULL DEFAULT '',
    serie INTEGER,
    numero INTEGER,
    data_ref TEXT NOT NULL DEFAULT '',
    ano_mes TEXT NOT NULL DEFAULT '',
    titulo TEXT NOT NULL,
    detalhe TEXT NOT NULL DEFAULT '',
    n_item INTEGER
);
CREATE INDEX IF NOT EXISTS ix_pend_empresa ON pendencias(cnpj_empresa, ano_mes);

-- A situação definida pelo usuário sobrevive ao recálculo das regras.
CREATE TABLE IF NOT EXISTS pendencias_situacao (
    hash TEXT PRIMARY KEY,
    situacao TEXT NOT NULL,                    -- resolvida | ignorada
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""


def abrir(caminho: Path | str) -> sqlite3.Connection:
    """Abre (ou cria) o banco com as configurações recomendadas."""
    conexao = sqlite3.connect(str(caminho), timeout=30)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.execute("PRAGMA journal_mode = WAL")
    conexao.execute("PRAGMA synchronous = NORMAL")
    criar_schema(conexao)
    return conexao


def criar_schema(conexao: sqlite3.Connection) -> None:
    conexao.executescript(SCHEMA)
    conexao.execute(
        "INSERT INTO meta(chave, valor) VALUES ('versao_schema', ?) "
        "ON CONFLICT(chave) DO NOTHING",
        (str(VERSAO_SCHEMA),),
    )
    conexao.commit()


def banco_vazio(conexao: sqlite3.Connection) -> bool:
    return conexao.execute("SELECT 1 FROM notas LIMIT 1").fetchone() is None
