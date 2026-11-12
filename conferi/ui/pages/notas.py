"""Notas fiscais com filtros."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox

from conferi.core import consultas
from conferi.core.exporters.excel import exportar_relatorio
from conferi.core.money import fmt_brl

from .. import theme
from ..contexto import Contexto, cnpj, data_br, documento
from ..dialogs.nota_detalhe import DialogoNota
from ..tabela import Coluna, criar_tabela, linha_do_indice
from ..widgets import CampoBusca, Card, Combo, EstadoVazio, Pagina, Rotulado, botao, rotulo


def _situacao(r) -> str:
    if r["cancelada"]:
        return "cancelada"
    if r["tp_amb"] == 2:
        return "homologacao"
    return "ativa" if r["n_prot"] else "sem_protocolo"


SITUACOES = {
    "ativa": ("Autorizada", theme.GREEN, theme.GREEN_SOFT),
    "cancelada": ("Cancelada", theme.RED, theme.RED_SOFT),
    "homologacao": ("Homologação", theme.MUTED, theme.GREY_SOFT),
    "sem_protocolo": ("Sem protocolo", theme.AMBER, theme.AMBER_SOFT),
}


class PaginaNotas(Pagina):
    def __init__(self, ctx: Contexto):
        super().__init__("Documentos", "Notas fiscais")
        self.ctx = ctx
        self.cabecalho.adicionar(botao("Exportar Excel", "Ghost", "excel", self._exportar))

        self.vazio = EstadoVazio("notas", "Nenhuma nota importada",
                                 "Importe os XMLs dos clientes para ver as notas organizadas aqui.", "Importar XMLs",
                                 lambda: ctx.navegar.emit("importar", {}))
        self.layout_pagina.addWidget(self.vazio)

        self.card = Card()
        filtros = QHBoxLayout()
        filtros.setSpacing(12)
        self.f_cliente = Combo(220)
        self.f_periodo = Combo(170)
        self.f_papel = Combo(130)
        self.f_papel.preencher([("Todas", None), ("Saídas", "saidas"), ("Entradas", "entradas")])
        self.f_modelo = Combo(110)
        self.f_modelo.preencher([("Todos", None), ("NF-e", "55"), ("NFC-e", "65")])
        self.f_situacao = Combo(130)
        self.f_situacao.preencher([("Todas", None), ("Ativas", "ativas"), ("Canceladas", "canceladas")])
        self.busca = CampoBusca("Número, chave, nome ou CNPJ")
        for rot, campo in (("Cliente", self.f_cliente), ("Período", self.f_periodo), ("Tipo", self.f_papel),
                           ("Modelo", self.f_modelo), ("Situação", self.f_situacao)):
            filtros.addWidget(Rotulado(rot, campo))
            campo.currentIndexChanged.connect(self._carregar)
        filtros.addWidget(Rotulado("Buscar", self.busca), 1)
        self.busca.returnPressed.connect(self._carregar)
        self.busca.textChanged.connect(lambda t: self._carregar() if not t else None)
        self.card.corpo.addLayout(filtros)

        colunas = [
            Coluna("data_emissao", "Data", formato=data_br, largura=100),
            Coluna(lambda r: (r["modelo"], r["serie"], r["numero"]), "Documento",
                   formato=lambda v: documento(*v), largura=180),
            Coluna("emit_nome", "Emitente", largura=240, dica=lambda r: f"{r['emit_nome']}\n{cnpj(r['emit_doc'])}"),
            Coluna(lambda r: r["dest_nome"] or ("Consumidor final" if r["modelo"] == "65" else ""), "Destinatário",
                   largura=240, dica=lambda r: f"{r['dest_nome']}\n{cnpj(r['dest_doc'])}"),
            Coluna("cfop_principal", "CFOP", largura=70),
            Coluna("v_nf", "Valor", formato=fmt_brl, alinhamento="direita", largura=130),
            Coluna(_situacao, "Situação", largura=130, pilula=lambda v: SITUACOES[v]),
            Coluna("pendencias", "Pendências", alinhamento="centro", largura=110, esticar=True,
                   pilula=lambda v: (str(v), theme.RED, theme.RED_SOFT) if v else ("—", theme.MUTED, "transparent")),
        ]
        self.tabela, self.modelo, self.proxy = criar_tabela(colunas, 42)
        self.tabela.doubleClicked.connect(self._abrir)
        self.card.corpo.addWidget(self.tabela, 1)
        rodape = QHBoxLayout()
        self.lb_total = rotulo("", "Small")
        rodape.addWidget(self.lb_total)
        rodape.addStretch(1)
        rodape.addWidget(rotulo("Dê dois cliques numa nota para ver itens, pagamentos e pendências.", "Small"))
        self.card.corpo.addLayout(rodape)
        self.layout_pagina.addWidget(self.card, 1)

        ctx.dados_alterados.connect(self.atualizar)
        self.atualizar()

    def aplicar_filtros(self, filtros: dict) -> None:
        self.atualizar()
        for combo, chave in ((self.f_cliente, "cnpj"), (self.f_periodo, "ano_mes")):
            if chave in filtros:
                combo.blockSignals(True)
                combo.selecionar(filtros[chave])
                combo.blockSignals(False)
        self._carregar()

    def atualizar(self, *_args) -> None:
        con = self.ctx.con
        self.f_cliente.preencher([("Todos os clientes", None)]
                                 + [(r["nome"], r["cnpj"]) for r in consultas.lista_clientes(con)])
        self.f_periodo.preencher([("Todos os períodos", None)]
                                 + [(consultas.rotulo_periodo(p), p) for p in consultas.periodos(con)])
        self._carregar()

    def _filtro(self) -> consultas.FiltroNotas:
        return consultas.FiltroNotas(
            cnpj=self.f_cliente.currentData(), ano_mes=self.f_periodo.currentData(),
            papel=self.f_papel.currentData(), modelo=self.f_modelo.currentData(),
            situacao=self.f_situacao.currentData(), busca=self.busca.text(), limite=20000)

    def _carregar(self, *_args) -> None:
        linhas = consultas.listar_notas(self.ctx.con, self._filtro())
        vazio = not linhas and not consultas.periodos(self.ctx.con)
        self.vazio.setVisible(vazio)
        self.card.setVisible(not vazio)
        self.modelo.definir_linhas(linhas)
        ativas = [r for r in linhas if not r["cancelada"]]
        qtd = f"{len(linhas):,}".replace(",", ".")
        texto = f"{qtd} notas · {fmt_brl(sum(r['v_nf'] for r in ativas))} em notas ativas"
        if len(linhas) >= 20000:
            texto += " · mostrando as 20.000 mais recentes; use os filtros para refinar"
        self.lb_total.setText(texto)

    def _abrir(self, indice) -> None:
        linha = linha_do_indice(indice, self.modelo, self.proxy)
        DialogoNota(self.ctx, linha["chave"], self).exec()

    def _exportar(self) -> None:
        cnpj_sel = self.f_cliente.currentData()
        nome = self.f_cliente.currentText() if cnpj_sel else ""
        sugestao = f"Notas {nome or 'clientes'} {self.f_periodo.currentData() or 'todos'}.xlsx".replace("/", "-")
        pasta = self.ctx.ambiente.config.ultima_pasta_exportacao or str(Path.home())
        destino, _ = QFileDialog.getSaveFileName(self, "Salvar relatório em Excel", str(Path(pasta) / sugestao),
                                                 "Excel (*.xlsx)")
        if not destino:
            return
        self.ctx.ambiente.config.ultima_pasta_exportacao = str(Path(destino).parent)
        self.ctx.ambiente.config.salvar()
        am = self.f_periodo.currentData()
        ambiente = self.ctx.ambiente

        def tarefa():
            con = ambiente.conectar()
            try:
                return exportar_relatorio(con, destino, cnpj_sel, am, nome)
            finally:
                con.close()

        self.ctx.executar(tarefa, lambda caminho: QMessageBox.information(
            self, "Relatório gerado", f"O relatório foi salvo em:\n{caminho}"),
            lambda erro: QMessageBox.critical(self, "Erro ao exportar", erro))
