"""Detalhes de uma nota: partes, totais, itens, pagamentos, eventos e pendências."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QTabWidget, QVBoxLayout, QWidget

from conferi.core import consultas
from conferi.core.money import fmt_brl
from conferi.core.rules import REGRAS

from .. import theme
from ..contexto import Contexto, cnpj, data_br
from ..tabela import Coluna, criar_tabela, pilula_nivel
from ..widgets import Badge, Card, botao, rotulo

PAGAMENTOS = {"01": "Dinheiro", "02": "Cheque", "03": "Cartão de crédito", "04": "Cartão de débito",
              "05": "Crédito loja", "10": "Vale alimentação", "11": "Vale refeição", "15": "Boleto",
              "16": "Depósito", "17": "Pix", "18": "Transferência", "90": "Sem pagamento", "99": "Outros"}


class DialogoNota(QDialog):
    def __init__(self, ctx: Contexto, chave: str, parent=None):
        super().__init__(parent)
        dados = consultas.detalhes_nota(ctx.con, chave)
        n = dados["nota"]
        self.chave = chave
        tipo = "NFC-e" if n["modelo"] == "65" else "NF-e"
        self.setWindowTitle(f"{tipo} {n['numero']}")
        self.resize(1100, 760)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(14)

        topo = QHBoxLayout()
        titulos = QVBoxLayout()
        titulos.setSpacing(2)
        titulos.addWidget(rotulo(f"{tipo.upper()} · SÉRIE {n['serie']} · {data_br(n['data_emissao'])}", "Kicker"))
        titulos.addWidget(rotulo(f"{tipo} {n['numero']}", "PageTitle"))
        linha_chave = QHBoxLayout()
        lb = rotulo(" ".join(chave[i:i + 4] for i in range(0, 44, 4)), "Small")
        lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        linha_chave.addWidget(lb)
        linha_chave.addWidget(botao("Copiar chave", "Text", "copiar", self._copiar, theme.GOLD))
        linha_chave.addStretch(1)
        titulos.addLayout(linha_chave)
        topo.addLayout(titulos, 1)
        if n["cancelada"]:
            topo.addWidget(Badge("Cancelada", theme.RED, theme.RED_SOFT))
        elif n["tp_amb"] == 2:
            topo.addWidget(Badge("Homologação", theme.MUTED, theme.GREY_SOFT))
        elif n["n_prot"]:
            topo.addWidget(Badge("Autorizada", theme.GREEN, theme.GREEN_SOFT))
        else:
            topo.addWidget(Badge("Sem protocolo", theme.AMBER, theme.AMBER_SOFT))
        lay.addLayout(topo)

        partes = QHBoxLayout()
        partes.setSpacing(14)
        for titulo, nome, doc, uf in (("Emitente", n["emit_nome"], n["emit_doc"], n["emit_uf"]),
                                      ("Destinatário", n["dest_nome"] or "Consumidor final", n["dest_doc"], n["dest_uf"])):
            c = Card()
            c.corpo.setSpacing(2)
            c.corpo.addWidget(rotulo(titulo.upper(), "SectionLabel"))
            c.corpo.addWidget(rotulo(nome or "—", "CardTitle"))
            c.corpo.addWidget(rotulo(f"{cnpj(doc) or 'sem documento'}{' · ' + uf if uf else ''}", "Small"))
            partes.addWidget(c, 1)
        totais = Card()
        grade = QGridLayout()
        grade.setHorizontalSpacing(18)
        grade.setVerticalSpacing(4)
        valores = [("Produtos", n["v_prod"]), ("Desconto", n["v_desc"]), ("Frete", n["v_frete"]),
                   ("Outras", n["v_outro"]), ("ICMS", n["v_icms"]), ("IPI", n["v_ipi"])]
        for i, (r, v) in enumerate(valores):
            grade.addWidget(rotulo(r, "Small"), i % 3, (i // 3) * 2)
            grade.addWidget(rotulo(fmt_brl(v)), i % 3, (i // 3) * 2 + 1)
        totais.corpo.addWidget(rotulo("TOTAL DA NOTA", "SectionLabel"))
        totais.corpo.addWidget(rotulo(fmt_brl(n["v_nf"]), "KpiValue"))
        totais.corpo.addLayout(grade)
        partes.addWidget(totais, 1)
        lay.addLayout(partes)

        abas = QTabWidget()
        itens, m_itens, _ = criar_tabela([
            Coluna("n_item", "#", largura=46, alinhamento="direita"),
            Coluna("codigo", "Código", largura=100),
            Coluna("descricao", "Descrição", largura=320),
            Coluna("ncm", "NCM", largura=90),
            Coluna("cfop", "CFOP", largura=70),
            Coluna("quantidade", "Qtde", largura=90, alinhamento="direita",
                   formato=lambda v: _num(v)),
            Coluna("valor_unitario", "Unitário", largura=110, alinhamento="direita",
                   formato=lambda v: _num(v, 2)),
            Coluna("v_prod", "Total", formato=fmt_brl, largura=120, alinhamento="direita"),
            Coluna(lambda r: "sim" if r["ibscbs_presente"] else "nao", "IBS/CBS", largura=100, esticar=True,
                   pilula=lambda v: ("Informado", theme.GREEN, theme.GREEN_SOFT) if v == "sim"
                   else ("Ausente", theme.MUTED, theme.GREY_SOFT)),
        ], 38)
        m_itens.definir_linhas(dados["itens"])
        abas.addTab(itens, f"Itens ({len(dados['itens'])})")

        pend, m_pend, _ = criar_tabela([
            Coluna("nivel", "Nível", largura=100, pilula=pilula_nivel),
            Coluna("regra", "Regra", largura=180, formato=lambda v: REGRAS.get(v, v)),
            Coluna("titulo", "Alerta", largura=360, negrito=True),
            Coluna("detalhe", "Detalhe", esticar=True, dica=lambda r: r["detalhe"]),
        ], 40)
        m_pend.definir_linhas(dados["pendencias"])
        abas.addTab(pend, f"Pendências ({len(dados['pendencias'])})")

        pag, m_pag, _ = criar_tabela([
            Coluna("t_pag", "Forma", largura=180, formato=lambda v: PAGAMENTOS.get(v, v)),
            Coluna("valor", "Valor", formato=fmt_brl, largura=120, alinhamento="direita"),
            Coluna("tp_integra", "Integrado ao caixa", largura=150,
                   formato=lambda v: {"1": "Sim", "2": "Não"}.get(v, "—")),
            Coluna("cnpj_credenciadora", "Credenciadora", formato=cnpj, largura=170),
            Coluna("c_aut", "Autorização", esticar=True),
        ], 38)
        m_pag.definir_linhas(dados["pagamentos"])
        abas.addTab(pag, f"Pagamentos ({len(dados['pagamentos'])})")

        ev, m_ev, _ = criar_tabela([
            Coluna("tipo", "Evento", largura=200,
                   formato=lambda v: {"110111": "Cancelamento", "110112": "Cancelamento por substituição",
                                      "110110": "Carta de correção"}.get(v, v)),
            Coluna("dh_evento", "Quando", formato=lambda v: data_br(v[:10]), largura=110),
            Coluna("c_stat", "Situação", largura=90),
            Coluna("justificativa", "Justificativa", esticar=True),
        ], 38)
        m_ev.definir_linhas(dados["eventos"])
        abas.addTab(ev, f"Eventos ({len(dados['eventos'])})")

        info = QWidget()
        il = QGridLayout(info)
        il.setContentsMargins(4, 14, 4, 4)
        il.setHorizontalSpacing(24)
        il.setVerticalSpacing(8)
        campos = [("Natureza da operação", n["nat_op"]),
                  ("Tipo", "Saída" if n["tp_nf"] == 1 else "Entrada"),
                  ("Destino", {1: "Interna", 2: "Interestadual", 3: "Exterior"}.get(n["id_dest"], "—")),
                  ("Finalidade", {1: "Normal", 2: "Complementar", 3: "Ajuste", 4: "Devolução"}.get(n["fin_nfe"], "—")),
                  ("Protocolo", n["n_prot"] or "—"), ("Código de situação", n["c_stat"] or "—"),
                  ("Arquivo de origem", n["arquivo_origem"])]
        for i, (r, v) in enumerate(campos):
            il.addWidget(rotulo(r, "Small"), i, 0)
            val = rotulo(str(v), quebra=True)
            il.addWidget(val, i, 1)
        il.setColumnStretch(1, 1)
        il.setRowStretch(len(campos), 1)
        abas.addTab(info, "Dados gerais")
        if dados["pendencias"]:
            abas.setCurrentIndex(1)
        lay.addWidget(abas, 1)

        rodape = QHBoxLayout()
        rodape.addStretch(1)
        rodape.addWidget(botao("Fechar", "Primary", ao_clicar=self.accept))
        lay.addLayout(rodape)

    def _copiar(self) -> None:
        QGuiApplication.clipboard().setText(self.chave)


def _num(texto: str, casas: int | None = None) -> str:
    try:
        valor = float(texto)
    except (TypeError, ValueError):
        return texto or ""
    if casas is None:
        casas = 0 if valor.is_integer() else 3
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
