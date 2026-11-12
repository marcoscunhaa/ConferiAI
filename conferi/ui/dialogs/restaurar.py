"""Escolha de um backup para restaurar."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QMessageBox, QVBoxLayout

from conferi.core import backup

from ..contexto import Contexto
from ..widgets import Banner, botao, rotulo


class DialogoRestaurar(QDialog):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Restaurar backup")
        self.resize(560, 480)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(12)
        lay.addWidget(rotulo("BACKUP", "Kicker"))
        lay.addWidget(rotulo("Restaurar uma cópia", "PageTitle"))
        lay.addWidget(rotulo(f"Pasta: {ctx.ambiente.pasta_backup}", "Small", quebra=True))
        lay.addWidget(Banner("A base atual será guardada com outro nome antes da restauração. As notas importadas "
                             "depois do backup podem ser recuperadas importando os XMLs de novo.", "Banner", "info"))
        self.lista = QListWidget()
        self.lista.setStyleSheet("QListWidget { background: white; border: 1px solid #E7E1D6; border-radius: 8px; }"
                                 "QListWidget::item { padding: 10px; }"
                                 "QListWidget::item:selected { background: #EEF1F5; color: #16233A; }")
        for info in backup.listar_backups(ctx.ambiente.pasta_backup):
            item = QListWidgetItem(f"{info.rotulo}    ·    {info.tamanho / 1024 / 1024:.1f} MB")
            item.setData(256, str(info.caminho))
            self.lista.addItem(item)
        if self.lista.count():
            self.lista.setCurrentRow(0)
        lay.addWidget(self.lista, 1)
        rodape = QHBoxLayout()
        rodape.addStretch(1)
        rodape.addWidget(botao("Cancelar", "Ghost", ao_clicar=self.reject))
        self.bt = botao("Restaurar", "Primary", "restaurar", self._restaurar)
        self.bt.setEnabled(self.lista.count() > 0)
        rodape.addWidget(self.bt)
        lay.addLayout(rodape)

    def _restaurar(self) -> None:
        item = self.lista.currentItem()
        if not item:
            return
        caminho = item.data(256)
        if QMessageBox.question(self, "Confirmar restauração",
                                f"Restaurar o backup de {item.text().split('·')[0].strip()}?") != \
                QMessageBox.StandardButton.Yes:
            return
        self.ctx.fechar()
        try:
            preservado = backup.restaurar(caminho, self.ctx.ambiente.banco)
        except Exception as erro:  # noqa: BLE001
            self.ctx.reconectar()
            QMessageBox.critical(self, "Não foi possível restaurar", str(erro))
            return
        self.ctx.reconectar()
        msg = "Backup restaurado com sucesso."
        if preservado:
            msg += f"\n\nA base anterior foi guardada em:\n{preservado}"
        QMessageBox.information(self, "Restauração concluída", msg)
        self.ctx.avisar_alteracao()
        self.accept()
