"""Operações de alto nível usadas pela interface (sem dependência de Qt)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from . import backup, db
from .config import AppConfig, caminho_banco, pasta_dados
from .importer import Cancelado, Progresso, ResultadoImportacao, importar
from .rules import recalcular_pendencias
from .sources import FontePastasArquivos


@dataclass
class Ambiente:
    config: AppConfig
    banco: Path

    @classmethod
    def carregar(cls) -> "Ambiente":
        return cls(AppConfig.carregar(), caminho_banco())

    def conectar(self) -> sqlite3.Connection:
        return db.abrir(self.banco)

    @property
    def pasta_backup(self) -> Path:
        return Path(self.config.backup.pasta) if self.config.backup.pasta else pasta_dados() / "backups"

    # ------------------------------------------------------------- backup
    def fazer_backup(self) -> Path | None:
        if not self.banco.exists():
            return None
        destino = backup.fazer_backup(self.banco, self.pasta_backup, self.config.backup.manter)
        self.config.backup.ultimo_backup = datetime.now().isoformat(timespec="seconds")
        self.config.salvar()
        return destino

    def backup_vencido(self, horas: int = 24) -> bool:
        ultimo = self.config.backup.ultimo_backup
        if not ultimo:
            return True
        try:
            return datetime.now() - datetime.fromisoformat(ultimo) > timedelta(hours=horas)
        except ValueError:
            return True

    def ultimo_backup_rotulo(self) -> str:
        ultimo = self.config.backup.ultimo_backup
        if not ultimo:
            return "Nenhum backup ainda"
        try:
            quando = datetime.fromisoformat(ultimo)
        except ValueError:
            return "Nenhum backup ainda"
        hoje = datetime.now().date()
        if quando.date() == hoje:
            return f"Hoje, {quando:%H:%M}"
        if quando.date() == hoje - timedelta(days=1):
            return f"Ontem, {quando:%H:%M}"
        return quando.strftime("%d/%m/%Y %H:%M")

    # ------------------------------------------------------------- importação
    def importar(self, caminhos: list[str | Path], progresso: Progresso | None = None,
                 cancelado: Cancelado | None = None) -> ResultadoImportacao:
        """Faz backup (se houver dados), importa e recalcula as pendências."""
        if self.config.backup.automatico and self.banco.exists():
            con = self.conectar()
            vazio = db.banco_vazio(con)
            con.close()
            if not vazio:
                self.fazer_backup()
        con = self.conectar()
        try:
            resultado = importar(con, FontePastasArquivos(caminhos), progresso, cancelado)
            recalcular_pendencias(con, self.config.regras)
        finally:
            con.close()
        return resultado

    def recalcular(self) -> int:
        con = self.conectar()
        try:
            return recalcular_pendencias(con, self.config.regras)
        finally:
            con.close()
