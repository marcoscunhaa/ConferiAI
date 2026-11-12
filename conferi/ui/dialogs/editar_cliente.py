"""Edição dos dados internos de uma empresa (apelido, regime, observações)."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QVBoxLayout

from conferi.core import clientes
from conferi.core.rules import recalcular_pendencias

from ..contexto import Contexto, cnpj
from ..widgets import Combo, botao, rotulo


class DialogoEditarCliente(QDialog):
    def __init__(self, ctx: Contexto, cnpj_empresa: str, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.cnpj = cnpj_empresa
        e = ctx.con.execute("SELECT * FROM empresas WHERE cnpj = ?", (cnpj_empresa,)).fetchone()
        self.setWindowTitle("Dados do cliente")
        self.resize(560, 470)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(12)
        lay.addWidget(rotulo("CLIENTE", "Kicker"))
        lay.addWidget(rotulo(e["razao_social"] or cnpj(e["cnpj"]), "CardTitle"))
        crt = clientes.CRT_DESCRICAO.get(e["crt"], "não informado")
        lay.addWidget(rotulo(f"{cnpj(e['cnpj'])} · {e['municipio']}/{e['uf']} · regime nas notas: {crt}", "Small"))

        form = QFormLayout()
        form.setSpacing(12)
        self.apelido = QLineEdit(e["apelido"])
        self.apelido.setPlaceholderText("Como o escritório chama este cliente")
        self.regime = Combo()
        self.regime.preencher([(r or "Não informado", r) for r in clientes.REGIMES], manter=False)
        self.regime.selecionar(e["regime"] or clientes.regime_sugerido(e["crt"]))
        self.obs = QPlainTextEdit(e["observacoes"])
        self.obs.setFixedHeight(90)
        self.cliente = QCheckBox("É cliente do escritório")
        self.cliente.setChecked(bool(e["is_cliente"]))
        form.addRow("Apelido", self.apelido)
        form.addRow("Regime", self.regime)
        form.addRow("Observações", self.obs)
        lay.addLayout(form)
        lay.addWidget(self.cliente)
        lay.addStretch(1)
        rodape = QHBoxLayout()
        rodape.addStretch(1)
        rodape.addWidget(botao("Cancelar", "Ghost", ao_clicar=self.reject))
        rodape.addWidget(botao("Salvar", "Primary", "check", self._salvar))
        lay.addLayout(rodape)

    def _salvar(self) -> None:
        anterior = self.ctx.con.execute("SELECT is_cliente FROM empresas WHERE cnpj = ?", (self.cnpj,)).fetchone()[0]
        self.ctx.con.execute(
            "UPDATE empresas SET apelido = ?, regime = ?, observacoes = ?, is_cliente = ? WHERE cnpj = ?",
            (self.apelido.text().strip(), self.regime.currentData() or "", self.obs.toPlainText().strip(),
             int(self.cliente.isChecked()), self.cnpj),
        )
        self.ctx.con.commit()
        if bool(anterior) != self.cliente.isChecked():
            recalcular_pendencias(self.ctx.con, self.ctx.ambiente.config.regras)
        self.accept()
