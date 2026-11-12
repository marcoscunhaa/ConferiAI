"""Configurações: backup, regras, dados e demonstração."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDate, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from conferi import __version__
from conferi.core import backup
from conferi.core.config import pasta_dados
from conferi.core.rules import carregar_tabela_ncm

from ..contexto import Contexto
from ..dialogs.restaurar import DialogoRestaurar
from ..widgets import Banner, Card, Pagina, botao, rotulo


class PaginaConfiguracoes(Pagina):
    def __init__(self, ctx: Contexto):
        super().__init__("Preferências", "Configurações", rolagem=True)
        self.ctx = ctx
        cfg = ctx.ambiente.config

        colunas = QHBoxLayout()
        colunas.setSpacing(16)
        esquerda, direita = QVBoxLayout(), QVBoxLayout()
        esquerda.setSpacing(16)
        direita.setSpacing(16)

        # ---------------- Backup
        c = Card("Backup")
        c.corpo.addWidget(rotulo("O banco em uso fica nesta máquina. Só as cópias vão para a pasta escolhida, que pode "
                                 "ser do Google Drive, OneDrive, servidor ou disco externo.", "Muted", quebra=True))
        form = QFormLayout()
        form.setSpacing(12)
        self.pasta_bk = QLineEdit(str(ctx.ambiente.pasta_backup))
        self.pasta_bk.setReadOnly(True)
        linha = QHBoxLayout()
        linha.addWidget(self.pasta_bk, 1)
        linha.addWidget(botao("Alterar", "Ghost", "pasta", self._escolher_pasta_backup))
        form.addRow("Pasta", linha)
        self.manter = QSpinBox()
        self.manter.setRange(2, 60)
        self.manter.setValue(cfg.backup.manter)
        self.manter.setSuffix(" cópias")
        form.addRow("Manter", self.manter)
        self.auto = QCheckBox("Backup automático antes de importar, ao fechar e uma vez por dia")
        self.auto.setChecked(cfg.backup.automatico)
        form.addRow("", self.auto)
        c.corpo.addLayout(form)
        self.lb_ultimo = rotulo("", "Small")
        c.corpo.addWidget(self.lb_ultimo)
        acoes = QHBoxLayout()
        acoes.addWidget(botao("Restaurar backup…", "Ghost", "restaurar", self._restaurar))
        acoes.addStretch(1)
        acoes.addWidget(botao("Fazer backup agora", "Primary", "backup", self._backup_agora))
        c.corpo.addLayout(acoes)
        esquerda.addWidget(c)

        # ---------------- Dados
        d = Card("Dados e integridade")
        self.lb_base = rotulo("", "Small", quebra=True)
        d.corpo.addWidget(self.lb_base)
        acoes = QHBoxLayout()
        acoes.addWidget(botao("Abrir pasta da base", "Ghost", "pasta",
                              lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(pasta_dados())))))
        acoes.addWidget(botao("Verificar integridade", "Ghost", "escudo", self._verificar))
        acoes.addStretch(1)
        acoes.addWidget(botao("Recalcular pendências", "Ghost", "atualizar", self._recalcular))
        d.corpo.addLayout(acoes)
        esquerda.addWidget(d)

        # ---------------- Demonstração
        demo = Card("Dados de demonstração")
        demo.corpo.addWidget(rotulo(
            "Gera uma pasta com XMLs fictícios de três clientes, com problemas conhecidos (lacunas, total divergente, "
            "CFOP, NCM, IBS/CBS, canceladas, repetidas, arquivo corrompido) e um arquivo da Sefaz para testar a "
            "conferência. Útil para treinar e demonstrar.", "Muted", quebra=True))
        demo.corpo.addWidget(botao("Gerar e importar demonstração", "Ghost", "faisca", self._demo))
        esquerda.addWidget(demo)
        esquerda.addStretch(1)

        # ---------------- Regras
        r = Card("Regras de conferência")
        r.corpo.addWidget(rotulo("As regras da reforma tributária ainda estão em ajuste. Confirme os parâmetros nas "
                                 "notas técnicas vigentes antes de usar os alertas de IBS/CBS.", "Muted", quebra=True))
        form = QFormLayout()
        form.setSpacing(12)
        self.tolerancia = QDoubleSpinBox()
        self.tolerancia.setPrefix("R$ ")
        self.tolerancia.setDecimals(2)
        self.tolerancia.setRange(0, 100)
        self.tolerancia.setSingleStep(0.05)
        self.tolerancia.setValue(cfg.regras.tolerancia_total_centavos / 100)
        form.addRow("Tolerância nos totais", self.tolerancia)
        self.ibs_ativo = QCheckBox("Conferir os campos de IBS/CBS")
        self.ibs_ativo.setChecked(cfg.regras.ibscbs_ativo)
        form.addRow("", self.ibs_ativo)
        self.ibs_inicio = QDateEdit()
        self.ibs_inicio.setCalendarPopup(True)
        self.ibs_inicio.setDisplayFormat("dd/MM/yyyy")
        self.ibs_inicio.setDate(QDate.fromString(cfg.regras.ibscbs_inicio, "yyyy-MM-dd"))
        form.addRow("A partir de", self.ibs_inicio)
        crts = set(cfg.regras.ibscbs_crts)
        self.crt3 = QCheckBox("Regime normal (CRT 3)")
        self.crt3.setChecked("3" in crts)
        self.crt1 = QCheckBox("Simples Nacional (CRT 1 e 2)")
        self.crt1.setChecked("1" in crts)
        self.crt4 = QCheckBox("MEI (CRT 4)")
        self.crt4.setChecked("4" in crts)
        caixa = QVBoxLayout()
        for chk in (self.crt3, self.crt1, self.crt4):
            caixa.addWidget(chk)
        form.addRow("Aplicar a emitentes do", caixa)
        self.ncm = QLineEdit(cfg.regras.tabela_ncm)
        self.ncm.setReadOnly(True)
        self.ncm.setPlaceholderText("Sem tabela: confere só o formato (8 dígitos)")
        linha = QHBoxLayout()
        linha.addWidget(self.ncm, 1)
        linha.addWidget(botao("Selecionar", "Ghost", "arquivo", self._escolher_ncm))
        linha.addWidget(botao("Limpar", "Text", ao_clicar=lambda: self.ncm.setText("")))
        form.addRow("Tabela NCM vigente", linha)
        r.corpo.addLayout(form)
        r.corpo.addWidget(Banner("A tabela NCM pode ser baixada no portal do Siscomex (JSON) ou salva como CSV com o "
                                 "código na primeira coluna.", "BannerInfo", "info"))
        acoes = QHBoxLayout()
        acoes.addStretch(1)
        acoes.addWidget(botao("Salvar e recalcular", "Primary", "check", self._salvar_regras))
        r.corpo.addLayout(acoes)
        direita.addWidget(r)

        sobre = Card("Sobre")
        sobre.corpo.addWidget(rotulo(f"Conferi AI · versão {__version__} (MVP)"))
        sobre.corpo.addWidget(rotulo("MARCOS C. DATA · Fortaleza, CE", "Small"))
        sobre.corpo.addWidget(rotulo("Os alertas são pontos para conferência a partir dos XMLs importados e não "
                                     "substituem a análise do profissional responsável.", "Small", quebra=True))
        direita.addWidget(sobre)
        direita.addStretch(1)

        colunas.addLayout(esquerda, 1)
        colunas.addLayout(direita, 1)
        self.layout_pagina.addLayout(colunas)
        self.layout_pagina.addStretch(1)

        self.manter.valueChanged.connect(self._salvar_backup)
        self.auto.toggled.connect(self._salvar_backup)
        ctx.dados_alterados.connect(self.atualizar)
        self.atualizar()

    # ------------------------------------------------------------------
    def atualizar(self) -> None:
        amb = self.ctx.ambiente
        self.lb_ultimo.setText(f"Último backup: {amb.ultimo_backup_rotulo()}")
        tamanho = amb.banco.stat().st_size / 1024 / 1024 if amb.banco.exists() else 0
        notas = self.ctx.con.execute("SELECT COUNT(*) FROM notas").fetchone()[0]
        self.lb_base.setText(f"Base local: {amb.banco}\n{notas:,} notas · {tamanho:.1f} MB".replace(",", "."))

    def _salvar_backup(self, *_args) -> None:
        cfg = self.ctx.ambiente.config
        cfg.backup.manter = self.manter.value()
        cfg.backup.automatico = self.auto.isChecked()
        cfg.salvar()

    def _escolher_pasta_backup(self) -> None:
        pasta = QFileDialog.getExistingDirectory(self, "Pasta para os backups", str(self.ctx.ambiente.pasta_backup))
        if not pasta:
            return
        if Path(pasta).resolve() == pasta_dados().resolve():
            QMessageBox.warning(self, "Escolha outra pasta", "Use uma pasta diferente da pasta da base local.")
            return
        self.ctx.ambiente.config.backup.pasta = pasta
        self.ctx.ambiente.config.salvar()
        self.pasta_bk.setText(pasta)

    def _backup_agora(self) -> None:
        try:
            destino = self.ctx.ambiente.fazer_backup()
        except Exception as erro:  # noqa: BLE001
            QMessageBox.critical(self, "Backup não realizado", str(erro))
            return
        self.atualizar()
        self.ctx.avisar_alteracao()
        if destino:
            QMessageBox.information(self, "Backup concluído", f"Cópia salva em:\n{destino}")

    def _restaurar(self) -> None:
        DialogoRestaurar(self.ctx, self).exec()

    def _verificar(self) -> None:
        ok, msg = backup.verificar_integridade(self.ctx.ambiente.banco)
        if ok:
            QMessageBox.information(self, "Base íntegra", "A verificação não encontrou problemas na base local.")
        else:
            QMessageBox.warning(self, "Problema na base",
                                f"A verificação encontrou um problema:\n{msg}\n\nUse “Restaurar backup…”.")

    def _recalcular(self) -> None:
        total = self.ctx.ambiente.recalcular()
        self.ctx.avisar_alteracao()
        QMessageBox.information(self, "Pendências recalculadas", f"{total} alertas gerados.")

    def _escolher_ncm(self) -> None:
        arquivo, _ = QFileDialog.getOpenFileName(self, "Tabela NCM", str(Path.home()),
                                                 "Tabela NCM (*.json *.csv *.txt)")
        if not arquivo:
            return
        codigos = carregar_tabela_ncm(arquivo)
        if not codigos:
            QMessageBox.warning(self, "Tabela não reconhecida", "Nenhum código NCM de 8 dígitos foi encontrado.")
            return
        self.ncm.setText(arquivo)
        QMessageBox.information(self, "Tabela carregada", f"{len(codigos):,} códigos encontrados.".replace(",", "."))

    def _salvar_regras(self) -> None:
        regras = self.ctx.ambiente.config.regras
        regras.tolerancia_total_centavos = round(self.tolerancia.value() * 100)
        regras.ibscbs_ativo = self.ibs_ativo.isChecked()
        regras.ibscbs_inicio = self.ibs_inicio.date().toString("yyyy-MM-dd")
        crts = []
        if self.crt3.isChecked():
            crts.append("3")
        if self.crt1.isChecked():
            crts += ["1", "2"]
        if self.crt4.isChecked():
            crts.append("4")
        regras.ibscbs_crts = crts
        regras.tabela_ncm = self.ncm.text()
        self.ctx.ambiente.config.salvar()
        self._recalcular()

    def _demo(self) -> None:
        from conferi.testing.cenario import gerar_cenario

        pasta = QFileDialog.getExistingDirectory(self, "Onde criar a pasta de demonstração", str(Path.home()))
        if not pasta:
            return
        destino = Path(pasta) / "Conferi AI - demonstracao"
        gerar_cenario(destino)
        QMessageBox.information(
            self, "Demonstração criada",
            f"A pasta foi criada em:\n{destino}\n\nA importação vai começar agora. Para testar a conferência com a "
            "Sefaz, use o arquivo “sefaz_padaria_outubro.csv” com a Padaria Pão Dourado em outubro de 2026.")
        self.ctx.navegar.emit("importar", {"caminhos": [str(destino)]})
