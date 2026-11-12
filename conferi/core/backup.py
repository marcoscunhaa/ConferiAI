"""Backup e restauração da base local.

- A cópia é feita pela API de backup do SQLite, consistente mesmo com o programa aberto.
- O banco em uso nunca fica na pasta sincronizada; só as cópias vão para lá.
- Antes de restaurar, o backup é testado; a base com problema é preservada com outro nome.
"""

from __future__ import annotations

import gzip
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PREFIXO = "conferi_backup_"
SUFIXO = ".db.gz"


@dataclass
class InfoBackup:
    caminho: Path
    criado_em: datetime
    tamanho: int

    @property
    def rotulo(self) -> str:
        return self.criado_em.strftime("%d/%m/%Y às %H:%M")


def verificar_integridade(caminho_banco: Path | str) -> tuple[bool, str]:
    caminho_banco = Path(caminho_banco)
    if not caminho_banco.exists():
        return True, "base ainda não criada"
    try:
        con = sqlite3.connect(f"file:{caminho_banco}?mode=ro", uri=True, timeout=10)
        try:
            resultado = con.execute("PRAGMA quick_check").fetchone()[0]
            con.execute("SELECT COUNT(*) FROM notas").fetchone()
        finally:
            con.close()
    except sqlite3.DatabaseError as erro:
        return False, str(erro)
    return (resultado == "ok"), resultado


def fazer_backup(caminho_banco: Path | str, pasta_destino: Path | str, manter: int = 10) -> Path:
    caminho_banco = Path(caminho_banco)
    pasta = Path(pasta_destino)
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = pasta / f"{PREFIXO}{carimbo}{SUFIXO}"

    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "copia.db"
        origem = sqlite3.connect(str(caminho_banco), timeout=30)
        alvo = sqlite3.connect(str(copia))
        try:
            origem.backup(alvo)
        finally:
            alvo.close()
            origem.close()
        parcial = destino.with_suffix(".parcial")
        with open(copia, "rb") as f_in, gzip.open(parcial, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.replace(parcial, destino)

    for antigo in listar_backups(pasta)[manter:]:
        try:
            antigo.caminho.unlink()
        except OSError:
            pass
    return destino


def listar_backups(pasta: Path | str) -> list[InfoBackup]:
    pasta = Path(pasta)
    if not pasta.exists():
        return []
    itens = []
    for arq in pasta.glob(f"{PREFIXO}*{SUFIXO}"):
        carimbo = arq.name[len(PREFIXO):-len(SUFIXO)]
        try:
            criado = datetime.strptime(carimbo, "%Y-%m-%d_%H%M%S")
        except ValueError:
            continue
        itens.append(InfoBackup(arq, criado, arq.stat().st_size))
    itens.sort(key=lambda b: b.criado_em, reverse=True)
    return itens


def testar_backup(backup: Path | str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        alvo = Path(tmp) / "teste.db"
        try:
            with gzip.open(backup, "rb") as f_in, open(alvo, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        except (OSError, EOFError) as erro:
            return False, f"arquivo de backup ilegível ({erro})"
        return verificar_integridade(alvo)


def restaurar(backup: Path | str, caminho_banco: Path | str) -> Path | None:
    """Restaura o backup. Todas as conexões com o banco devem estar fechadas.

    Retorna o caminho onde a base anterior foi preservada (ou None se não existia).
    """
    ok, motivo = testar_backup(backup)
    if not ok:
        raise ValueError(f"O backup não passou na verificação: {motivo}")
    caminho_banco = Path(caminho_banco)
    preservado = None
    if caminho_banco.exists():
        carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        preservado = caminho_banco.with_name(f"{caminho_banco.stem}_anterior_{carimbo}.db")
        os.replace(caminho_banco, preservado)
    for extra in ("-wal", "-shm"):
        resto = Path(str(caminho_banco) + extra)
        if resto.exists():
            resto.unlink()
    parcial = caminho_banco.with_suffix(".restaurando")
    with gzip.open(backup, "rb") as f_in, open(parcial, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.replace(parcial, caminho_banco)
    return preservado


def restaurar_mais_recente_valido(pasta: Path | str, caminho_banco: Path | str) -> InfoBackup | None:
    for info in listar_backups(pasta):
        if testar_backup(info.caminho)[0]:
            restaurar(info.caminho, caminho_banco)
            return info
    return None
