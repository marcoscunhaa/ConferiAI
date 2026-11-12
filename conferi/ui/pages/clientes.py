"""Carteira de clientes."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout

from conferi.core import consultas
from conferi.core.money import fmt_brl

from .. import theme
from ..contexto import Contexto, cnpj, data_br
from ..dialogs.confirmar_clientes import DialogoConfirmarClientes
from ..dialogs.editar_cliente import DialogoEditarCliente
from ..tabela import Coluna, criar_tabela, linha_do_indice, linhas_selecionadas
from ..widgets import CampoBusca, Card, Combo, EstadoVazio, Pagina, Rotulado, botao, rotulo


def _qtd(cor, fundo):
    return lambda v: (str(v), cor, fundo) if v else ("—", theme.MUTED, "transparent")


class PaginaClientes(Pagina):
    def __init__(self, ctx: Contexto):
        super().__init__("Carteira", "Clientes",
                         "Empresas identificadas nas notas e confirmadas como clientes do escritório.")
        self.ctx = ctx
        self.cabecalho.adicionar(botao("Revisar empresas", "Ghost", "clientes", self._revisar))

        self.vazio = EstadoVazio("clientes", "Nenhum cliente ainda",
                                 "Os clientes aparecem aqui depois da primeira importação, quando você confirma quais "
                                 "CNPJs são clientes do escritório.", "Importar XMLs",
                                 lambda: ctx.navegar.emit("importar", {}))
        self.layout_pagina.addWidget(self.vazio)

        self.card = Card()
        filtros = QHBoxLayout()
        filtros.setSpacing(12)
        self.periodo = Combo(190)
        self.periodo.currentIndexChanged.connect(self.atualizar)
        self.busca = CampoBusca("Buscar por nome ou CNPJ")
        self.busca.textChanged.connect(self._filtrar)
        filtros.addWidget(Rotulado("Período", self.periodo))
        filtros.addWidget(Rotulado("Buscar", self.busca), 1)
        filtros.addStretch(1)
        self.card.corpo.addLayout(filtros)

        colunas = [
            Coluna("nome", "Cliente", negrito=True, largura=280),
            Coluna("cnpj", "CNPJ", formato=cnpj, largura=170),
            Coluna("regime", "Regime", formato=lambda v: v or "Não informado", largura=140),
            Coluna("uf", "UF", largura=50),
            Coluna("notas_saida", "Saídas", alinhamento="direita", largura=80),
            Coluna("notas_entrada", "Entradas", alinhamento="direita", largura=90),
            Coluna("faturamento", "Faturamento", formato=fmt_brl, alinhamento="direita", largura=150),
            Coluna("compras", "Compras", formato=fmt_brl, alinhamento="direita", largura=150),
            Coluna("pend_alta", "Altas", alinhamento="centro", largura=80, pilula=_qtd(theme.RED, theme.RED_SOFT)),
            Coluna("pend_media", "Médias", alinhamento="centro", largura=80,
                   pilula=_qtd(theme.AMBER, theme.AMBER_SOFT)),
            Coluna("ultima_nota", "Última nota", formato=data_br, largura=110, esticar=True),
        ]
        self.tabela, self.modelo, self.proxy = criar_tabela(colunas, 46)
        self.tabela.doubleClicked.connect(self._editar)
        self.card.corpo.addWidget(self.tabela, 1)

        acoes = QHBoxLayout()
        self.lb_total = rotulo("", "Small")
        acoes.addWidget(self.lb_total)
        acoes.addStretch(1)
        acoes.addWidget(botao("Editar dados", "Ghost", "config", self._editar_selecionado))
        acoes.addWidget(botao("Ver notas", "Ghost", "notas", self._ver_notas))
        acoes.addWidget(botao("Ver pendências", "Primary", "pendencias", self._ver_pendencias))
        self.card.corpo.addLayout(acoes)
        self.layout_pagina.addWidget(self.card, 1)

        self._todas: list[dict] = []
        ctx.dados_alterados.connect(self.atualizar)
        self.atualizar()

    def atualizar(self, *_args) -> None:
        periodos = consultas.periodos(self.ctx.con)
        self.periodo.preencher([("Todos os períodos", None)] + [(consultas.rotulo_periodo(p), p) for p in periodos])
        self._todas = consultas.resumo_clientes(self.ctx.con, self.periodo.currentData())
        vazio = not self._todas
        self.vazio.setVisible(vazio)
        self.card.setVisible(not vazio)
        self._filtrar()

    def _filtrar(self, *_args) -> None:
        termo = self.busca.text().strip().lower()
        digitos = "".join(c for c in termo if c.isdigit())
        linhas = [r for r in self._todas
                  if not termo or termo in (r["nome"] or "").lower() or (digitos and digitos in r["cnpj"])]
        self.modelo.definir_linhas(linhas)
        total = sum(r["faturamento"] for r in linhas)
        self.lb_total.setText(f"{len(linhas)} clientes · faturamento somado {fmt_brl(total)}")

    def _selecionado(self):
        sel = linhas_selecionadas(self.tabela, self.modelo, self.proxy)
        return sel[0] if sel else None

    def _editar(self, indice) -> None:
        linha = linha_do_indice(indice, self.modelo, self.proxy)
        if DialogoEditarCliente(self.ctx, linha["cnpj"], self).exec():
            self.ctx.avisar_alteracao()

    def _editar_selecionado(self) -> None:
        linha = self._selecionado()
        if linha and DialogoEditarCliente(self.ctx, linha["cnpj"], self).exec():
            self.ctx.avisar_alteracao()

    def _ver_notas(self) -> None:
        linha = self._selecionado()
        self.ctx.navegar.emit("notas", {"cnpj": linha["cnpj"] if linha else None,
                                        "ano_mes": self.periodo.currentData()})

    def _ver_pendencias(self) -> None:
        linha = self._selecionado()
        self.ctx.navegar.emit("pendencias", {"cnpj": linha["cnpj"] if linha else None,
                                             "ano_mes": self.periodo.currentData()})

    def _revisar(self) -> None:
        DialogoConfirmarClientes(self.ctx, self, somente_pendentes=False).exec()
        self.ctx.avisar_alteracao()
