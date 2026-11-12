"""Pendências: alertas de conferência com filtros e tratamento."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QButtonGroup, QCheckBox, QFileDialog, QHBoxLayout, QMessageBox, QVBoxLayout

from conferi.core import consultas
from conferi.core.exporters.excel import exportar_relatorio
from conferi.core.exporters.pdf import exportar_pendencias
from conferi.core.rules import REGRAS, definir_situacao

from .. import theme
from ..contexto import Contexto, data_br, documento
from ..dialogs.nota_detalhe import DialogoNota
from ..tabela import Coluna, criar_tabela, linha_do_indice, linhas_selecionadas, pilula_nivel
from ..widgets import CampoBusca, Card, Combo, EstadoVazio, Pagina, Rotulado, botao, rotulo

SITUACAO_PILULA = {
    "aberta": ("Aberta", theme.NAVY, theme.TINT),
    "resolvida": ("Resolvida", theme.GREEN, theme.GREEN_SOFT),
    "ignorada": ("Ignorada", theme.MUTED, theme.GREY_SOFT),
}


class PaginaPendencias(Pagina):
    def __init__(self, ctx: Contexto):
        super().__init__("Conferência", "Pendências",
                         "Alertas para conferência. A decisão fiscal continua sendo do profissional responsável.")
        self.ctx = ctx
        self.cabecalho.adicionar(botao("Exportar Excel", "Ghost", "excel", self._exportar_excel))
        self.cabecalho.adicionar(botao("Relatório PDF", "Primary", "pdf", self._exportar_pdf))

        self.vazio = EstadoVazio("check_circulo", "Nada para conferir por enquanto",
                                 "As pendências aparecem aqui depois que você importa os XMLs dos clientes.",
                                 "Importar XMLs", lambda: ctx.navegar.emit("importar", {}))
        self.layout_pagina.addWidget(self.vazio)

        self.card = Card()
        # Níveis (chips)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.grupo_nivel = QButtonGroup(self)
        self.chips = {}
        for nivel, texto in ((None, "Todas"), ("alta", "Alta"), ("media", "Média"), ("baixa", "Baixa")):
            b = botao(texto, "Chip")
            b.setCheckable(True)
            self.grupo_nivel.addButton(b)
            self.chips[nivel] = b
            b.clicked.connect(self._carregar)
            chips.addWidget(b)
        self.chips[None].setChecked(True)
        chips.addStretch(1)
        self.mostrar_info = QCheckBox("Mostrar informativos (canceladas, homologação)")
        self.mostrar_info.toggled.connect(self._carregar)
        chips.addWidget(self.mostrar_info)
        self.card.corpo.addLayout(chips)

        filtros = QHBoxLayout()
        filtros.setSpacing(12)
        self.f_cliente = Combo(220)
        self.f_periodo = Combo(170)
        self.f_regra = Combo(190)
        self.f_regra.preencher([("Todas as regras", None)] + [(v, k) for k, v in REGRAS.items()])
        self.f_situacao = Combo(140)
        self.f_situacao.preencher([("Abertas", "abertas"), ("Resolvidas", "resolvidas"),
                                   ("Ignoradas", "ignoradas"), ("Todas", "todas")])
        self.busca = CampoBusca("Buscar no alerta, número ou cliente")
        for rot, campo in (("Cliente", self.f_cliente), ("Período", self.f_periodo), ("Regra", self.f_regra),
                           ("Situação", self.f_situacao)):
            filtros.addWidget(Rotulado(rot, campo))
            campo.currentIndexChanged.connect(self._carregar)
        filtros.addWidget(Rotulado("Buscar", self.busca), 1)
        self.busca.textChanged.connect(self._carregar)
        self.card.corpo.addLayout(filtros)

        colunas = [
            Coluna("nivel", "Nível", largura=100, pilula=pilula_nivel),
            Coluna("empresa_nome", "Cliente", largura=210, negrito=True),
            Coluna(lambda r: (r["modelo"], r["numero"], r["serie"]), "Documento", largura=170,
                   formato=lambda v: documento(*v)),
            Coluna("data_ref", "Data", formato=data_br, largura=96),
            Coluna("regra", "Regra", formato=lambda v: REGRAS.get(v, v), largura=170),
            Coluna("titulo", "Alerta", largura=380, dica=lambda r: f"{r['titulo']}\n\n{r['detalhe']}"),
            Coluna("situacao", "Situação", largura=110, esticar=True, pilula=lambda v: SITUACAO_PILULA.get(v)),
        ]
        self.tabela, self.modelo, self.proxy = criar_tabela(colunas, 44)
        self.tabela.doubleClicked.connect(self._abrir_nota)
        self.tabela.selectionModel().selectionChanged.connect(self._mostrar_detalhe)
        self.card.corpo.addWidget(self.tabela, 1)

        # Detalhe da pendência selecionada
        self.detalhe = Card(margem=16)
        self.detalhe.setStyleSheet(f"#Card {{ background: {theme.PAPER}; }}")
        self.lb_det_titulo = rotulo("", "CardTitle", quebra=True)
        self.lb_det_texto = rotulo("", quebra=True)
        self.lb_det_chave = rotulo("", "Small")
        caixa = QVBoxLayout()
        caixa.setSpacing(4)
        caixa.addWidget(self.lb_det_titulo)
        caixa.addWidget(self.lb_det_texto)
        caixa.addWidget(self.lb_det_chave)
        self.detalhe.corpo.addLayout(caixa)
        self.card.corpo.addWidget(self.detalhe)
        self.detalhe.hide()

        acoes = QHBoxLayout()
        self.lb_total = rotulo("", "Small")
        acoes.addWidget(self.lb_total)
        acoes.addStretch(1)
        acoes.addWidget(botao("Abrir nota", "Ghost", "olho", self._abrir_nota_selecionada))
        acoes.addWidget(botao("Reabrir", "Ghost", "restaurar", lambda: self._marcar(None)))
        acoes.addWidget(botao("Ignorar", "Ghost", "x", lambda: self._marcar("ignorada")))
        acoes.addWidget(botao("Marcar como resolvida", "Primary", "check", lambda: self._marcar("resolvida")))
        self.card.corpo.addLayout(acoes)
        self.layout_pagina.addWidget(self.card, 1)

        ctx.dados_alterados.connect(self.atualizar)
        self.atualizar()

    # ------------------------------------------------------------------
    def aplicar_filtros(self, filtros: dict) -> None:
        self.atualizar()
        for combo, chave in ((self.f_cliente, "cnpj"), (self.f_periodo, "ano_mes")):
            combo.blockSignals(True)
            combo.selecionar(filtros.get(chave))
            combo.blockSignals(False)
        nivel = filtros.get("nivel")
        self.chips.get(nivel, self.chips[None]).setChecked(True)
        self.f_situacao.blockSignals(True)
        self.f_situacao.selecionar("abertas")
        self.f_situacao.blockSignals(False)
        self._carregar()

    def atualizar(self) -> None:
        con = self.ctx.con
        self.f_cliente.preencher([("Todos os clientes", None)]
                                 + [(r["nome"], r["cnpj"]) for r in consultas.lista_clientes(con)])
        self.f_periodo.preencher([("Todos os períodos", None)]
                                 + [(consultas.rotulo_periodo(p), p) for p in consultas.periodos(con)])
        self._carregar()

    def _nivel(self) -> str | None:
        for nivel, b in self.chips.items():
            if b.isChecked():
                return nivel
        return None

    def _filtro(self, nivel: bool = True) -> consultas.FiltroPendencias:
        return consultas.FiltroPendencias(
            cnpj=self.f_cliente.currentData(), ano_mes=self.f_periodo.currentData(),
            nivel=self._nivel() if nivel else None, regra=self.f_regra.currentData(),
            situacao=self.f_situacao.currentData(), incluir_info=self.mostrar_info.isChecked(),
            busca=self.busca.text())

    def _carregar(self, *_args) -> None:
        con = self.ctx.con
        tem_dados = bool(consultas.periodos(con))
        self.vazio.setVisible(not tem_dados)
        self.card.setVisible(tem_dados)
        if not tem_dados:
            return
        todas = consultas.listar_pendencias(con, self._filtro(nivel=False))
        contagem = {n: sum(1 for p in todas if p["nivel"] == n) for n in ("alta", "media", "baixa")}
        self.chips[None].setText(f"Todas  {len(todas)}")
        for nivel, rot in (("alta", "Alta"), ("media", "Média"), ("baixa", "Baixa")):
            self.chips[nivel].setText(f"{rot}  {contagem[nivel]}")
        nivel = self._nivel()
        linhas = [p for p in todas if nivel is None or p["nivel"] == nivel]
        self.modelo.definir_linhas(linhas)
        self.lb_total.setText(f"{len(linhas)} pendência(s) · selecione várias com Ctrl ou Shift")
        self.detalhe.hide()

    def _mostrar_detalhe(self, *_args) -> None:
        sel = linhas_selecionadas(self.tabela, self.modelo, self.proxy)
        if len(sel) != 1:
            self.detalhe.setVisible(len(sel) > 1)
            if len(sel) > 1:
                self.lb_det_titulo.setText(f"{len(sel)} pendências selecionadas")
                self.lb_det_texto.setText("Use os botões abaixo para tratá-las de uma vez.")
                self.lb_det_chave.setText("")
            return
        p = sel[0]
        self.lb_det_titulo.setText(p["titulo"])
        self.lb_det_texto.setText(p["detalhe"])
        self.lb_det_chave.setText(f"Chave de acesso: {p['chave']}" if p["chave"] else "")
        self.detalhe.show()

    def _marcar(self, situacao: str | None) -> None:
        sel = linhas_selecionadas(self.tabela, self.modelo, self.proxy)
        if not sel:
            QMessageBox.information(self, "Nenhuma pendência selecionada",
                                    "Selecione uma ou mais pendências na tabela.")
            return
        definir_situacao(self.ctx.con, [p["hash"] for p in sel], situacao)
        self.ctx.avisar_alteracao()

    def _abrir_nota(self, indice) -> None:
        linha = linha_do_indice(indice, self.modelo, self.proxy)
        if linha["chave"]:
            DialogoNota(self.ctx, linha["chave"], self).exec()

    def _abrir_nota_selecionada(self) -> None:
        sel = linhas_selecionadas(self.tabela, self.modelo, self.proxy)
        if sel and sel[0]["chave"]:
            DialogoNota(self.ctx, sel[0]["chave"], self).exec()
        elif sel:
            QMessageBox.information(self, "Sem nota associada",
                                    "Esta pendência se refere a uma faixa de numeração, não a uma nota específica.")

    # ------------------------------------------------------------------ exportação
    def _destino(self, titulo: str, sugestao: str, filtro_arquivo: str) -> str | None:
        pasta = self.ctx.ambiente.config.ultima_pasta_exportacao or str(Path.home())
        destino, _ = QFileDialog.getSaveFileName(self, titulo, str(Path(pasta) / sugestao), filtro_arquivo)
        if destino:
            self.ctx.ambiente.config.ultima_pasta_exportacao = str(Path(destino).parent)
            self.ctx.ambiente.config.salvar()
        return destino or None

    def _exportar_pdf(self) -> None:
        nome = self.f_cliente.currentText() if self.f_cliente.currentData() else ""
        destino = self._destino("Salvar relatório de pendências", f"Pendencias {nome or 'clientes'}.pdf",
                                "PDF (*.pdf)")
        if not destino:
            return
        filtro = self._filtro()
        ambiente = self.ctx.ambiente

        def tarefa():
            con = ambiente.conectar()
            try:
                return exportar_pendencias(con, destino, filtro, nome)
            finally:
                con.close()

        self.ctx.executar(tarefa, lambda c: QMessageBox.information(self, "Relatório gerado", f"Salvo em:\n{c}"),
                          lambda e: QMessageBox.critical(self, "Erro ao gerar o PDF", e))

    def _exportar_excel(self) -> None:
        cnpj_sel = self.f_cliente.currentData()
        nome = self.f_cliente.currentText() if cnpj_sel else ""
        destino = self._destino("Salvar relatório em Excel", f"Conferencia {nome or 'clientes'}.xlsx",
                                "Excel (*.xlsx)")
        if not destino:
            return
        am = self.f_periodo.currentData()
        ambiente = self.ctx.ambiente

        def tarefa():
            con = ambiente.conectar()
            try:
                return exportar_relatorio(con, destino, cnpj_sel, am, nome)
            finally:
                con.close()

        self.ctx.executar(tarefa, lambda c: QMessageBox.information(self, "Relatório gerado", f"Salvo em:\n{c}"),
                          lambda e: QMessageBox.critical(self, "Erro ao exportar", e))
