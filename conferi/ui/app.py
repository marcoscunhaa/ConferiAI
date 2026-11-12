"""Ponto de entrada da interface."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from conferi import APP_AUTHOR, APP_NAME
from conferi.core import backup
from conferi.core.servico import Ambiente

from . import theme
from .contexto import Contexto


def _verificar_base(ambiente: Ambiente) -> bool:
    """Confere a base ao abrir e oferece restaurar o último backup válido. Retorna False para encerrar."""
    ok, motivo = backup.verificar_integridade(ambiente.banco)
    if ok:
        return True
    backups = backup.listar_backups(ambiente.pasta_backup)
    if not backups:
        QMessageBox.critical(None, "Problema na base de dados",
                             f"A base local apresentou um problema ({motivo}) e não há backups disponíveis.\n\n"
                             f"Arquivo: {ambiente.banco}\n\nRenomeie o arquivo e reimporte os XMLs.")
        return False
    resposta = QMessageBox.question(
        None, "Problema na base de dados",
        f"Encontramos um problema na base local ({motivo}).\n\nDeseja restaurar o backup de "
        f"{backups[0].rotulo}? A base atual será preservada com outro nome.")
    if resposta != QMessageBox.StandardButton.Yes:
        return False
    info = backup.restaurar_mais_recente_valido(ambiente.pasta_backup, ambiente.banco)
    if info is None:
        QMessageBox.critical(None, "Restauração não concluída", "Nenhum backup válido foi encontrado.")
        return False
    QMessageBox.information(None, "Base restaurada", f"Backup de {info.rotulo} restaurado com sucesso.")
    return True


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_AUTHOR)
    theme.carregar_fontes()
    fonte = QFont(theme.BODY)
    fonte.setPixelSize(14)
    app.setFont(fonte)
    app.setStyle("Fusion")
    paleta = app.palette()
    for papel, cor in ((QPalette.ColorRole.Window, theme.PAPER), (QPalette.ColorRole.Base, "#FFFFFF"),
                       (QPalette.ColorRole.AlternateBase, "#FBFAF7"), (QPalette.ColorRole.Text, theme.INK),
                       (QPalette.ColorRole.WindowText, theme.INK), (QPalette.ColorRole.Button, "#FFFFFF"),
                       (QPalette.ColorRole.ButtonText, theme.NAVY), (QPalette.ColorRole.Highlight, theme.TINT),
                       (QPalette.ColorRole.HighlightedText, theme.INK), (QPalette.ColorRole.ToolTipBase, theme.NAVY),
                       (QPalette.ColorRole.ToolTipText, "#FFFFFF")):
        paleta.setColor(papel, QColor(cor))
    app.setPalette(paleta)
    app.setStyleSheet(theme.folha_de_estilos())

    ambiente = Ambiente.carregar()
    if not _verificar_base(ambiente):
        return 1

    ctx = Contexto(ambiente)
    if ambiente.config.backup.automatico and ambiente.backup_vencido():
        try:
            if ctx.con.execute("SELECT 1 FROM notas LIMIT 1").fetchone():
                ambiente.fazer_backup()
        except Exception:  # noqa: BLE001
            pass

    from .janela import JanelaPrincipal

    janela = JanelaPrincipal(ctx)
    janela.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
