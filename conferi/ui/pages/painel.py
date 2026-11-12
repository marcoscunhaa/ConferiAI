"""Painel: visão geral do escritório no período."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from conferi.core import consultas
from conferi.core.money import fmt_brl_curto
from conferi.core.rules import REGRAS

from .. import theme
from ..contexto import Contexto, data_br
from ..icons import pixmap
from ..tabela import Coluna, criar_tabela, linha_do_indice
from ..widgets import BarraProporcao, Card, Combo, EstadoVazio, KpiCard, Pagina, botao, rotulo


def _pilula_qtd(cor: str, fundo: str):
    return lambda v: (str(v), cor, fundo) if v else ("—", theme.MUTED, "transparent")


class PaginaPainel(Pagina):
    def __init__(self, ctx: Contexto):
        super().__init__("Visão geral do escritório", "Painel", rolagem=True)
        self.ctx = ctx
        self.periodo = Combo(190)
        self.periodo.currentIndexChanged.connect(self.atualizar)
        self.cabecalho.adicionar(self.periodo)
        self.cabecalho.adicionar(botao("Importar XMLs", "Primary", "importar",
                                       lambda: ctx.navegar.emit("importar", {})))

        self.vazio = EstadoVazio(
            "camadas", "Comece importando os XMLs dos seus clientes",
            "Selecione uma pasta, arquivos XML ou .zip. O Conferi AI organiza tudo por empresa, remove notas "
            "repetidas e aponta o que precisa de atenção. Nada sai do seu computador.",
            "Importar XMLs", lambda: ctx.navegar.emit("importar", {}))
        self.layout_pagina.addWidget(self.vazio)

        self.conteudo = QWidget()
        corpo = QVBoxLayout(self.conteudo)
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(18)

        # Indicadores
        grade = QGridLayout()
        grade.setSpacing(14)
        self.k_clientes = KpiCard("Clientes", theme.NAVY, clicavel=True)
        self.k_fat = KpiCard("Faturamento dos clientes", theme.NAVY)
        self.k_alta = KpiCard("Pendências altas", theme.RED, clicavel=True)
        self.k_media = KpiCard("Médias e baixas", theme.AMBER, clicavel=True)
        self.k_notas = KpiCard("Notas no período", theme.GREEN, clicavel=True)
        self.k_clientes.clicado.connect(lambda: ctx.navegar.emit("clientes", {}))
        self.k_alta.clicado.connect(lambda: ctx.navegar.emit("pendencias", {"nivel": "alta",
                                                                             "ano_mes": self.periodo.currentData()}))
        self.k_media.clicado.connect(lambda: ctx.navegar.emit("pendencias", {"ano_mes": self.periodo.currentData()}))
        self.k_notas.clicado.connect(lambda: ctx.navegar.emit("notas", {"ano_mes": self.periodo.currentData()}))
        for i, k in enumerate((self.k_fat, self.k_alta, self.k_media, self.k_notas, self.k_clientes)):
            grade.addWidget(k, 0, i)
            grade.setColumnStretch(i, 5 if i == 0 else 4)
        corpo.addLayout(grade)

        linha = QHBoxLayout()
        linha.setSpacing(16)

        # Clientes por prioridade
        self.card_clientes = Card("Clientes que precisam de atenção",
                                  acao=botao("Ver todos", "Text", ao_clicar=lambda: ctx.navegar.emit("clientes", {})))
        self.card_clientes.corpo.addWidget(rotulo(
            "Ordenados pela prioridade: pendências altas primeiro, depois médias.", "Small"))
        colunas = [
            Coluna("nome", "Cliente", negrito=True, esticar=True),
            Coluna("regime", "Regime", largura=130, formato=lambda v: v or "—"),
            Coluna("faturamento", "Faturamento", formato=fmt_brl_curto, alinhamento="direita", largura=130),
            Coluna(lambda r: r["notas_saida"] + r["notas_entrada"], "Notas", alinhamento="direita", largura=80),
            Coluna("pend_alta", "Altas", largura=80, alinhamento="centro",
                   pilula=_pilula_qtd(theme.RED, theme.RED_SOFT)),
            Coluna("pend_media", "Médias", largura=80, alinhamento="centro",
                   pilula=_pilula_qtd(theme.AMBER, theme.AMBER_SOFT)),
            Coluna(lambda r: "atencao" if r["pend_alta"] else ("revisar" if r["pend_media"] else "ok"), "Situação",
                   largura=130, pilula=lambda v: {"atencao": ("Precisa de atenção", theme.RED, theme.RED_SOFT),
                                                  "revisar": ("Revisar", theme.AMBER, theme.AMBER_SOFT),
                                                  "ok": ("Em dia", theme.GREEN, theme.GREEN_SOFT)}[v]),
        ]
        self.tab_clientes, self.mod_clientes, self.prx_clientes = criar_tabela(colunas, 46)
        self.tab_clientes.setSortingEnabled(False)
        self.tab_clientes.setMinimumHeight(420)
        self.tab_clientes.doubleClicked.connect(self._abrir_cliente)
        self.card_clientes.corpo.addWidget(self.tab_clientes)
        linha.addWidget(self.card_clientes, 3)

        lateral = QVBoxLayout()
        lateral.setSpacing(16)
        self.card_regras = Card("Pendências por tipo")
        self.barra_niveis = BarraProporcao(10)
        self.card_regras.corpo.addWidget(self.barra_niveis)
        self.lista_regras = QVBoxLayout()
        self.lista_regras.setSpacing(6)
        self.card_regras.corpo.addLayout(self.lista_regras)
        lateral.addWidget(self.card_regras)

        self.card_import = Card("Últimas importações")
        self.lista_import = QVBoxLayout()
        self.lista_import.setSpacing(8)
        self.card_import.corpo.addLayout(self.lista_import)
        lateral.addWidget(self.card_import)
        lateral.addStretch(1)
        lado = QWidget()
        lado.setLayout(lateral)
        lado.setMinimumWidth(320)
        lado.setMaximumWidth(380)
        linha.addWidget(lado, 1)
        corpo.addLayout(linha)
        self.layout_pagina.addWidget(self.conteudo)
        self.layout_pagina.addStretch(1)

        ctx.dados_alterados.connect(self.atualizar)
        self.atualizar()

    # ------------------------------------------------------------------
    def _abrir_cliente(self, indice) -> None:
        linha = linha_do_indice(indice, self.mod_clientes, self.prx_clientes)
        self.ctx.navegar.emit("pendencias", {"cnpj": linha["cnpj"], "ano_mes": self.periodo.currentData()})

    def _limpar(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._limpar(item.layout())

    def atualizar(self, *_args) -> None:
        con = self.ctx.con
        periodos = consultas.periodos(con)
        if self.periodo.count() != len(periodos) + 1:
            self.periodo.preencher([(consultas.rotulo_periodo(p), p) for p in periodos]
                                   + [("Todos os períodos", None)], manter=False)
            if periodos:
                self.periodo.setCurrentIndex(0)
        vazio = not periodos
        self.vazio.setVisible(vazio)
        self.conteudo.setVisible(not vazio)
        self.periodo.setVisible(not vazio)
        if vazio:
            return

        am = self.periodo.currentData()
        k = consultas.kpis(con, am)
        self.k_clientes.definir(str(k.clientes), f"{k.clientes_com_pendencia} com pendências altas ou médias")
        self.k_fat.definir(fmt_brl_curto(k.faturamento), f"Compras: {fmt_brl_curto(k.compras)}")
        self.k_alta.definir(str(k.pendencias_alta), "lacunas, totais e CFOP")
        self.k_media.definir(str(k.pendencias_media + k.pendencias_baixa),
                             f"{k.pendencias_media} médias · {k.pendencias_baixa} baixas")
        self.k_notas.definir(f"{k.notas:,}".replace(",", "."), f"{k.canceladas} canceladas")

        self.mod_clientes.definir_linhas(consultas.resumo_clientes(con, am)[:12])

        self._limpar(self.lista_regras)
        self.barra_niveis.definir([(k.pendencias_alta, theme.RED), (k.pendencias_media, theme.AMBER),
                                   (k.pendencias_baixa, theme.BLUE)])
        regras = consultas.contagem_por_regra(con, am)
        if not regras:
            self.lista_regras.addWidget(rotulo("Nenhuma pendência aberta no período.", "Muted"))
        maior = max((r["qtd"] for r in regras), default=1)
        for r in regras[:8]:
            linha = QHBoxLayout()
            nome = rotulo(REGRAS.get(r["regra"], r["regra"]))
            linha.addWidget(nome, 1)
            barra = BarraProporcao(6)
            barra.setFixedWidth(90)
            barra.definir([(r["qtd"], theme.GOLD), (maior - r["qtd"], theme.LINE_SOFT)])
            linha.addWidget(barra)
            qtd = rotulo(str(r["qtd"]))
            qtd.setFixedWidth(34)
            qtd.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            linha.addWidget(qtd)
            self.lista_regras.addLayout(linha)

        self._limpar(self.lista_import)
        importacoes = consultas.ultimas_importacoes(con, 4)
        for imp in importacoes:
            item = QHBoxLayout()
            item.setSpacing(10)
            ic = QLabel()
            ic.setPixmap(pixmap("check_circulo", theme.GREEN, 18))
            ic.setAlignment(Qt.AlignmentFlag.AlignTop)
            item.addWidget(ic)
            textos = QVBoxLayout()
            textos.setSpacing(0)
            textos.addWidget(rotulo(f"{imp['notas_novas']} notas novas · {imp['duplicadas']} repetidas"))
            sub = f"{data_br(imp['iniciado_em'][:10])} às {imp['iniciado_em'][11:16]}"
            if imp["invalidos"]:
                sub += f" · {imp['invalidos']} arquivo(s) com problema"
            textos.addWidget(rotulo(sub, "Small"))
            item.addLayout(textos, 1)
            self.lista_import.addLayout(item)
        if not importacoes:
            self.lista_import.addWidget(rotulo("Nenhuma importação ainda.", "Muted"))
