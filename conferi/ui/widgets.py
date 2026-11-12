"""Componentes visuais reutilizáveis."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .icons import icone, pixmap


def rotulo(texto: str = "", nome: str | None = None, quebra: bool = False) -> QLabel:
    lb = QLabel(texto)
    if nome:
        lb.setObjectName(nome)
    if quebra:
        lb.setWordWrap(True)
    return lb


def botao(texto: str, tipo: str | None = None, icone_nome: str | None = None,
          ao_clicar: Callable | None = None, cor_icone: str | None = None) -> QPushButton:
    b = QPushButton(texto)
    if tipo:
        b.setObjectName(tipo)
    if icone_nome:
        cor = cor_icone or ("#FFFFFF" if tipo in ("Primary", "Gold") else theme.NAVY)
        b.setIcon(icone(icone_nome, cor, 16))
        b.setIconSize(QSize(16, 16))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if ao_clicar:
        b.clicked.connect(ao_clicar)
    return b


def sombra(widget: QWidget, raio: int = 24, opacidade: int = 18) -> None:
    efeito = QGraphicsDropShadowEffect(widget)
    efeito.setBlurRadius(raio)
    efeito.setOffset(0, 4)
    efeito.setColor(QColor(22, 35, 58, opacidade))
    widget.setGraphicsEffect(efeito)


class Card(QFrame):
    def __init__(self, titulo: str | None = None, parent: QWidget | None = None, margem: int = 20,
                 acao: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.corpo = QVBoxLayout(self)
        self.corpo.setContentsMargins(margem, margem - 2, margem, margem)
        self.corpo.setSpacing(12)
        if titulo:
            topo = QHBoxLayout()
            topo.setSpacing(8)
            self.titulo = rotulo(titulo, "CardTitle")
            topo.addWidget(self.titulo)
            topo.addStretch(1)
            if acao:
                topo.addWidget(acao)
            self.corpo.addLayout(topo)


class Separador(QFrame):
    def __init__(self, cor: str = theme.LINE):
        super().__init__()
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {cor}; border: none;")


class Badge(QLabel):
    """Pílula colorida: nível de pendência, situação, regime."""

    def __init__(self, texto: str = "", cor: str = theme.MUTED, fundo: str = theme.GREY_SOFT):
        super().__init__(texto)
        self.definir(texto, cor, fundo)

    def definir(self, texto: str, cor: str, fundo: str) -> None:
        self.setText(texto)
        self.setStyleSheet(
            f"background: {fundo}; color: {cor}; border-radius: 10px; padding: 3px 10px;"
            f"font-family: '{theme.SANS}'; font-size: 11px; font-weight: 500;")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class KpiCard(QFrame):
    """Cartão de indicador com barra lateral colorida."""

    clicado = Signal()

    def __init__(self, titulo: str, cor: str = theme.NAVY, clicavel: bool = False):
        super().__init__()
        self.setObjectName("Card")
        self._cor = cor
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        barra = QFrame()
        barra.setFixedWidth(4)
        barra.setStyleSheet(f"background: {cor}; border: none; border-top-left-radius: 12px;"
                            "border-bottom-left-radius: 12px;")
        lay.addWidget(barra)
        corpo = QVBoxLayout()
        corpo.setContentsMargins(16, 14, 16, 14)
        corpo.setSpacing(2)
        self.lb_titulo = rotulo(titulo.upper(), "KpiLabel")
        self.lb_valor = rotulo("—", "KpiValue")
        if cor != theme.NAVY:
            self.lb_valor.setStyleSheet(f"color: {cor};")
        self.lb_sub = rotulo("", "KpiSub", quebra=True)
        corpo.addWidget(self.lb_titulo)
        corpo.addWidget(self.lb_valor)
        corpo.addWidget(self.lb_sub)
        corpo.addStretch(1)
        lay.addLayout(corpo, 1)
        self.setMinimumHeight(118)
        if clicavel:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def definir(self, valor: str, sub: str = "") -> None:
        self.lb_valor.setText(valor)
        self.lb_sub.setText(sub)

    def mousePressEvent(self, ev):  # noqa: N802
        self.clicado.emit()
        super().mousePressEvent(ev)


class CabecalhoPagina(QWidget):
    def __init__(self, kicker: str, titulo: str, subtitulo: str = ""):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(rotulo(kicker.upper(), "Kicker"))
        textos.addWidget(rotulo(titulo, "PageTitle"))
        if subtitulo:
            textos.addWidget(rotulo(subtitulo, "PageSubtitle", quebra=True))
        lay.addLayout(textos, 1)
        self.acoes = QHBoxLayout()
        self.acoes.setSpacing(10)
        lay.addLayout(self.acoes)
        lay.setAlignment(self.acoes, Qt.AlignmentFlag.AlignBottom)

    def adicionar(self, widget: QWidget) -> None:
        self.acoes.addWidget(widget)


class Pagina(QWidget):
    """Base das páginas: cabeçalho + corpo com rolagem opcional."""

    def __init__(self, kicker: str, titulo: str, subtitulo: str = "", rolagem: bool = False):
        super().__init__()
        self.setObjectName("PageBody")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        conteudo = QWidget()
        conteudo.setObjectName("PageBody")
        conteudo.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.layout_pagina = QVBoxLayout(conteudo)
        self.layout_pagina.setContentsMargins(32, 28, 32, 28)
        self.layout_pagina.setSpacing(18)
        self.cabecalho = CabecalhoPagina(kicker, titulo, subtitulo)
        self.layout_pagina.addWidget(self.cabecalho)
        if rolagem:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.Shape.NoFrame)
            area.setWidget(conteudo)
            externo.addWidget(area)
        else:
            externo.addWidget(conteudo)

    def atualizar(self) -> None:  # sobrescrito nas páginas
        pass


class Banner(QFrame):
    def __init__(self, texto: str = "", tipo: str = "Banner", icone_nome: str = "info"):
        super().__init__()
        self.setObjectName(tipo)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)
        cor = {"Banner": theme.GOLD, "BannerInfo": theme.NAVY, "BannerErro": theme.RED}.get(tipo, theme.NAVY)
        self.ic = QLabel()
        self.ic.setPixmap(pixmap(icone_nome, cor, 18))
        self.ic.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self.ic)
        self.texto = rotulo(texto, quebra=True)
        self.texto.setTextFormat(Qt.TextFormat.RichText)
        self.texto.setOpenExternalLinks(False)
        lay.addWidget(self.texto, 1)
        self.acoes = QHBoxLayout()
        lay.addLayout(self.acoes)

    def definir(self, texto: str) -> None:
        self.texto.setText(texto)


class EstadoVazio(QFrame):
    def __init__(self, icone_nome: str, titulo: str, texto: str, botao_texto: str | None = None,
                 ao_clicar: Callable | None = None):
        super().__init__()
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 48, 40, 48)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circulo = QLabel()
        circulo.setFixedSize(64, 64)
        circulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circulo.setPixmap(pixmap(icone_nome, theme.GOLD, 28))
        circulo.setStyleSheet(f"background: {theme.GOLD_SOFT}; border-radius: 32px;")
        lay.addWidget(circulo, alignment=Qt.AlignmentFlag.AlignHCenter)
        t = rotulo(titulo, "EmptyTitle")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        d = rotulo(texto, "Muted", quebra=True)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setMaximumWidth(520)
        lay.addWidget(d, alignment=Qt.AlignmentFlag.AlignHCenter)
        if botao_texto:
            lay.addSpacing(6)
            lay.addWidget(botao(botao_texto, "Primary", "importar", ao_clicar), alignment=Qt.AlignmentFlag.AlignHCenter)


class CampoBusca(QLineEdit):
    def __init__(self, dica: str = "Buscar…"):
        super().__init__()
        self.setPlaceholderText(dica)
        self.addAction(icone("busca", theme.MUTED, 16), QLineEdit.ActionPosition.LeadingPosition)
        self.setClearButtonEnabled(True)
        self.setMinimumWidth(220)


class Combo(QComboBox):
    """ComboBox com dados associados a cada opção."""

    def __init__(self, largura_minima: int = 160):
        super().__init__()
        self.setMinimumWidth(largura_minima)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def preencher(self, opcoes: list[tuple[str, object]], manter: bool = True) -> None:
        atual = self.currentData() if manter else None
        self.blockSignals(True)
        self.clear()
        for texto, dado in opcoes:
            self.addItem(texto, dado)
        indice = self.indice_do_dado(atual) if atual is not None else -1
        self.setCurrentIndex(indice if indice >= 0 else 0)
        self.blockSignals(False)

    def indice_do_dado(self, dado: object) -> int:
        for i in range(self.count()):
            if self.itemData(i) == dado:
                return i
        return -1

    def selecionar(self, dado: object) -> None:
        i = self.indice_do_dado(dado)
        if i >= 0:
            self.setCurrentIndex(i)


class Rotulado(QWidget):
    """Campo com legenda pequena acima (para barras de filtro)."""

    def __init__(self, legenda: str, campo: QWidget):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(rotulo(legenda.upper(), "SectionLabel"))
        lay.addWidget(campo)
        self.campo = campo


class Monograma(QWidget):
    """Círculo dourado com a letra C (marca)."""

    def __init__(self, tamanho: int = 36):
        super().__init__()
        self.setFixedSize(tamanho, tamanho)

    def paintEvent(self, _ev):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(theme.GOLD))
        r = self.rect().adjusted(1, 1, -1, -1)
        p.drawEllipse(r)
        fonte = p.font()
        fonte.setFamily(theme.SERIF)
        fonte.setPixelSize(int(self.height() * 0.55))
        p.setFont(fonte)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, "C")
        p.end()


class BarraProporcao(QWidget):
    """Barra horizontal empilhada (ex.: pendências por nível)."""

    def __init__(self, altura: int = 10):
        super().__init__()
        self.setFixedHeight(altura)
        self.partes: list[tuple[int, str]] = []

    def definir(self, partes: list[tuple[int, str]]) -> None:
        self.partes = partes
        self.update()

    def paintEvent(self, _ev):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        total = sum(v for v, _ in self.partes)
        r = self.rect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.LINE_SOFT))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        if total:
            x = 0.0
            for valor, cor in self.partes:
                if not valor:
                    continue
                w = r.width() * valor / total
                p.setBrush(QColor(cor))
                p.drawRoundedRect(int(x), 0, max(int(w) - 2, 2), r.height(), r.height() / 2, r.height() / 2)
                x += w
        p.end()
