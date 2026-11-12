"""Relatórios: Excel completo e PDF de pendências."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox, QVBoxLayout

from conferi.core import consultas
from conferi.core.exporters.excel import exportar_relatorio
from conferi.core.exporters.pdf import exportar_pendencias

from .. import theme
from ..contexto import Contexto
from ..icons import pixmap
from ..widgets import Banner, Card, Combo, Pagina, Rotulado, botao, rotulo


class CardRelatorio(Card):
    def __init__(self, icone_nome: str, titulo: str, descricao: str, itens: list[str]):
        super().__init__()
        topo = QHBoxLayout()
        topo.setSpacing(14)
        ic = QLabel()
        ic.setFixedSize(48, 48)
        ic.setPixmap(pixmap(icone_nome, theme.GOLD, 24))
        ic.setStyleSheet(f"background: {theme.GOLD_SOFT}; border-radius: 12px; padding: 12px;")
        topo.addWidget(ic)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(rotulo(titulo, "CardTitle"))
        textos.addWidget(rotulo(descricao, "Muted", quebra=True))
        topo.addLayout(textos, 1)
        self.corpo.addLayout(topo)
        lista = QVBoxLayout()
        lista.setSpacing(3)
        for item in itens:
            lista.addWidget(rotulo(f"•  {item}", "Small"))
        self.corpo.addLayout(lista)
        self.filtros = QHBoxLayout()
        self.filtros.setSpacing(12)
        self.corpo.addLayout(self.filtros)


class PaginaRelatorios(Pagina):
    def __init__(self, ctx: Contexto):
        super().__init__("Entregas", "Relatórios",
                         "Gere os arquivos para o analista ou para enviar ao cliente.", rolagem=True)
        self.ctx = ctx
        self.ultimo: Path | None = None

        linha = QHBoxLayout()
        linha.setSpacing(16)
        self.card_excel = CardRelatorio(
            "excel", "Relatório completo em Excel",
            "Uma planilha pronta para análise, com filtros em todas as abas.",
            ["Resumo com faturamento, compras e pendências", "Notas e itens", "Por fornecedor e por comprador",
             "Por CFOP, por NCM e por mês", "Pendências com situação"])
        self.ex_cliente, self.ex_periodo = Combo(220), Combo(180)
        self.card_excel.filtros.addWidget(Rotulado("Cliente", self.ex_cliente))
        self.card_excel.filtros.addWidget(Rotulado("Período", self.ex_periodo))
        self.card_excel.filtros.addStretch(1)
        self.card_excel.corpo.addWidget(botao("Gerar Excel", "Primary", "excel", self._gerar_excel))
        linha.addWidget(self.card_excel, 1)

        self.card_pdf = CardRelatorio(
            "pdf", "Relatório de pendências em PDF",
            "Documento para anexar ao atendimento ou enviar ao cliente pedindo correções.",
            ["Resumo por nível", "Cada alerta com documento, data e motivo", "Somente pendências abertas",
             "Identidade visual do Conferi AI"])
        self.pdf_cliente, self.pdf_periodo = Combo(220), Combo(180)
        self.card_pdf.filtros.addWidget(Rotulado("Cliente", self.pdf_cliente))
        self.card_pdf.filtros.addWidget(Rotulado("Período", self.pdf_periodo))
        self.card_pdf.filtros.addStretch(1)
        self.card_pdf.corpo.addWidget(botao("Gerar PDF", "Primary", "pdf", self._gerar_pdf))
        linha.addWidget(self.card_pdf, 1)
        self.layout_pagina.addLayout(linha)

        self.aviso = Banner("", "Banner", "check_circulo")
        self.aviso.acoes.addWidget(botao("Abrir arquivo", "Ghost", "olho", self._abrir_arquivo))
        self.aviso.acoes.addWidget(botao("Abrir pasta", "Ghost", "pasta", self._abrir_pasta))
        self.aviso.hide()
        self.layout_pagina.addWidget(self.aviso)
        self.layout_pagina.addStretch(1)

        ctx.dados_alterados.connect(self.atualizar)
        self.atualizar()

    def atualizar(self) -> None:
        con = self.ctx.con
        clientes = [("Todos os clientes", None)] + [(r["nome"], r["cnpj"]) for r in consultas.lista_clientes(con)]
        periodos = [(consultas.rotulo_periodo(p), p) for p in consultas.periodos(con)] + [("Todos os períodos", None)]
        for combo in (self.ex_cliente, self.pdf_cliente):
            combo.preencher(clientes)
        for combo in (self.ex_periodo, self.pdf_periodo):
            combo.preencher(periodos)

    def _destino(self, sugestao: str, filtro: str) -> str | None:
        pasta = self.ctx.ambiente.config.ultima_pasta_exportacao or str(Path.home())
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar relatório", str(Path(pasta) / sugestao), filtro)
        if destino:
            self.ctx.ambiente.config.ultima_pasta_exportacao = str(Path(destino).parent)
            self.ctx.ambiente.config.salvar()
        return destino or None

    def _concluido(self, caminho) -> None:
        self.ultimo = Path(caminho)
        self.aviso.definir(f"<b>Relatório gerado.</b> {self.ultimo}")
        self.aviso.show()

    def _gerar_excel(self) -> None:
        cnpj_sel, am = self.ex_cliente.currentData(), self.ex_periodo.currentData()
        nome = self.ex_cliente.currentText() if cnpj_sel else ""
        destino = self._destino(f"Relatorio {nome or 'clientes'} {am or 'geral'}.xlsx", "Excel (*.xlsx)")
        if not destino:
            return
        ambiente = self.ctx.ambiente

        def tarefa():
            con = ambiente.conectar()
            try:
                return exportar_relatorio(con, destino, cnpj_sel, am, nome)
            finally:
                con.close()

        self.ctx.executar(tarefa, self._concluido, lambda e: QMessageBox.critical(self, "Erro ao gerar", e))

    def _gerar_pdf(self) -> None:
        cnpj_sel, am = self.pdf_cliente.currentData(), self.pdf_periodo.currentData()
        nome = self.pdf_cliente.currentText() if cnpj_sel else ""
        destino = self._destino(f"Pendencias {nome or 'clientes'} {am or 'geral'}.pdf", "PDF (*.pdf)")
        if not destino:
            return
        filtro = consultas.FiltroPendencias(cnpj=cnpj_sel, ano_mes=am)
        ambiente = self.ctx.ambiente

        def tarefa():
            con = ambiente.conectar()
            try:
                return exportar_pendencias(con, destino, filtro, nome)
            finally:
                con.close()

        self.ctx.executar(tarefa, self._concluido, lambda e: QMessageBox.critical(self, "Erro ao gerar", e))

    def _abrir_arquivo(self) -> None:
        if self.ultimo:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ultimo)))

    def _abrir_pasta(self) -> None:
        if self.ultimo:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ultimo.parent)))
