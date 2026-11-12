"""Confirmação de quais empresas são clientes do escritório."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from conferi.core import clientes
from conferi.core.rules import recalcular_pendencias

from ..contexto import Contexto, cnpj
from ..widgets import Banner, botao, rotulo


class DialogoConfirmarClientes(QDialog):
    def __init__(self, ctx: Contexto, parent=None, somente_pendentes: bool = True):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Quem são seus clientes?")
        self.resize(1040, 640)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(14)
        lay.addWidget(rotulo("CONFIRMAÇÃO RÁPIDA", "Kicker"))
        lay.addWidget(rotulo("Quem são seus clientes?", "PageTitle"))
        lay.addWidget(rotulo(
            "Toda nota tem dois CNPJs: quem vendeu e quem comprou. Marque as empresas que são clientes do escritório; "
            "as demais serão tratadas como fornecedores ou compradores. Você só faz isso uma vez por empresa.",
            "Muted", quebra=True))
        lay.addWidget(Banner("As sugestões já vêm marcadas, com base em quantas notas cada CNPJ emitiu ou recebeu. "
                             "Ajuste o regime quando a nota não informar (Lucro Presumido ou Real).", "Banner", "faisca"))

        sugestoes = clientes.sugerir_clientes(ctx.con)
        if somente_pendentes:
            pendentes = [s for s in sugestoes if s.is_cliente is None]
            sugestoes = pendentes or sugestoes
        self.sugestoes = sugestoes

        self.tabela = QTableWidget(len(sugestoes), 7)
        self.tabela.setHorizontalHeaderLabels(["CLIENTE?", "EMPRESA", "CNPJ", "UF", "EMITIU", "RECEBEU", "REGIME"])
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.verticalHeader().setDefaultSectionSize(46)
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setShowGrid(False)
        cab = self.tabela.horizontalHeader()
        cab.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col, largura in ((0, 90), (2, 170), (3, 50), (4, 80), (5, 80), (6, 170)):
            self.tabela.setColumnWidth(col, largura)

        self.checks: list[QCheckBox] = []
        self.regimes: list[QComboBox] = []
        for i, s in enumerate(sugestoes):
            marcado = bool(s.is_cliente) if s.is_cliente is not None else s.sugerido
            chk = QCheckBox()
            chk.setChecked(marcado)
            celula = QWidget()
            cl = QHBoxLayout(celula)
            cl.setContentsMargins(18, 0, 0, 0)
            cl.addWidget(chk)
            self.tabela.setCellWidget(i, 0, celula)
            self.checks.append(chk)

            nome = QTableWidgetItem(s.nome or "(sem nome)")
            nome.setToolTip(s.motivo)
            fonte = nome.font()
            fonte.setBold(True)
            nome.setFont(fonte)
            self.tabela.setItem(i, 1, nome)
            self.tabela.setItem(i, 2, QTableWidgetItem(cnpj(s.cnpj)))
            self.tabela.setItem(i, 3, QTableWidgetItem(s.uf))
            for col, valor in ((4, s.como_emitente), (5, s.como_destinatario)):
                it = QTableWidgetItem(str(valor))
                it.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                self.tabela.setItem(i, col, it)
            combo = QComboBox()
            combo.addItems([r or "Não informado" for r in clientes.REGIMES])
            idx = clientes.REGIMES.index(s.regime) if s.regime in clientes.REGIMES else 0
            combo.setCurrentIndex(idx)
            self.tabela.setCellWidget(i, 6, combo)
            self.regimes.append(combo)
            if not marcado:
                for col in range(1, 6):
                    item = self.tabela.item(i, col)
                    if item:
                        item.setForeground(QBrush(QColor("#9AA3B2")))
        lay.addWidget(self.tabela, 1)

        rodape = QHBoxLayout()
        self.lb_total = rotulo("", "Small")
        rodape.addWidget(self.lb_total)
        rodape.addStretch(1)
        rodape.addWidget(botao("Marcar sugeridos", "Ghost", "faisca", self._marcar_sugeridos))
        rodape.addWidget(botao("Confirmar clientes", "Primary", "check", self._confirmar))
        lay.addLayout(rodape)
        for chk in self.checks:
            chk.toggled.connect(self._contar)
        self._contar()

    def _contar(self, *_args) -> None:
        total = sum(c.isChecked() for c in self.checks)
        self.lb_total.setText(f"{total} de {len(self.checks)} empresas marcadas como clientes")

    def _marcar_sugeridos(self) -> None:
        for chk, s in zip(self.checks, self.sugestoes):
            chk.setChecked(s.sugerido)

    def _confirmar(self) -> None:
        decisoes = {}
        for chk, combo, s in zip(self.checks, self.regimes, self.sugestoes):
            decisoes[s.cnpj] = (chk.isChecked(), clientes.REGIMES[combo.currentIndex()])
        clientes.salvar_clientes(self.ctx.con, decisoes)
        recalcular_pendencias(self.ctx.con, self.ctx.ambiente.config.regras)
        self.accept()

    def reject(self) -> None:
        # Fechou sem decidir: aplica as sugestões para não deixar empresas pendentes.
        clientes.confirmar_sugestoes_automaticamente(self.ctx.con)
        recalcular_pendencias(self.ctx.con, self.ctx.ambiente.config.regras)
        super().reject()
