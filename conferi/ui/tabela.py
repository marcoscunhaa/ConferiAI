"""Tabelas: modelo genérico, delegado de "pílulas" e fábrica de QTableView estilizada."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QAbstractItemView, QFrame, QHeaderView, QStyle, QStyledItemDelegate, QTableView

from . import theme

ROLE_BRUTO = Qt.ItemDataRole.UserRole + 1
ROLE_LINHA = Qt.ItemDataRole.UserRole + 2


@dataclass
class Coluna:
    chave: str | Callable[[Any], Any]
    titulo: str
    formato: Callable[[Any], str] | None = None
    alinhamento: str = "esquerda"           # esquerda | direita | centro
    largura: int | None = None
    pilula: Callable[[Any], tuple[str, str, str] | None] | None = None  # valor -> (texto, cor, fundo)
    negrito: bool = False
    dica: Callable[[Any], str] | None = None
    cor: Callable[[Any], str | None] | None = None
    esticar: bool = False


class ModeloTabela(QAbstractTableModel):
    def __init__(self, colunas: list[Coluna]):
        super().__init__()
        self.colunas = colunas
        self.linhas: list[Any] = []

    def definir_linhas(self, linhas: list[Any]) -> None:
        self.beginResetModel()
        self.linhas = list(linhas)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):  # noqa: N802
        return 0 if parent.isValid() else len(self.linhas)

    def columnCount(self, parent=QModelIndex()):  # noqa: N802
        return 0 if parent.isValid() else len(self.colunas)

    def _bruto(self, linha: Any, col: Coluna) -> Any:
        if callable(col.chave):
            return col.chave(linha)
        try:
            return linha[col.chave]
        except (KeyError, IndexError, TypeError):
            return getattr(linha, col.chave, None)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        linha = self.linhas[index.row()]
        col = self.colunas[index.column()]
        valor = self._bruto(linha, col)
        if role == Qt.ItemDataRole.DisplayRole:
            if col.pilula:
                return None
            return col.formato(valor) if col.formato else ("" if valor is None else str(valor))
        if role == ROLE_BRUTO:
            return valor
        if role == ROLE_LINHA:
            return linha
        if role == Qt.ItemDataRole.TextAlignmentRole:
            h = {"direita": Qt.AlignmentFlag.AlignRight, "centro": Qt.AlignmentFlag.AlignHCenter}.get(
                col.alinhamento, Qt.AlignmentFlag.AlignLeft)
            return int(h | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.FontRole and col.negrito:
            f = QFont(theme.BODY)
            f.setBold(True)
            f.setPixelSize(14)
            return f
        if role == Qt.ItemDataRole.ForegroundRole and col.cor:
            c = col.cor(valor)
            return QColor(c) if c else None
        if role == Qt.ItemDataRole.ToolTipRole:
            if col.dica:
                return col.dica(linha)
            if col.formato:
                return col.formato(valor)
            return None if valor is None else str(valor)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self.colunas[section].titulo.upper()
            if role == Qt.ItemDataRole.TextAlignmentRole:
                h = Qt.AlignmentFlag.AlignRight if self.colunas[section].alinhamento == "direita" else \
                    Qt.AlignmentFlag.AlignLeft
                return int(h | Qt.AlignmentFlag.AlignVCenter)
        return None

    def linha(self, indice_fonte: int) -> Any:
        return self.linhas[indice_fonte]


class Ordenador(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.setSortRole(ROLE_BRUTO)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def lessThan(self, esquerda, direita):  # noqa: N802
        a, b = esquerda.data(ROLE_BRUTO), direita.data(ROLE_BRUTO)
        if a is None:
            return True
        if b is None:
            return False
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


class DelegadoPilula(QStyledItemDelegate):
    """Desenha pílulas coloridas nas colunas que definem `pilula`."""

    def __init__(self, modelo: ModeloTabela, parent=None):
        super().__init__(parent)
        self.modelo = modelo

    def paint(self, painter: QPainter, option, index):
        col = self.modelo.colunas[index.column()]
        if not col.pilula:
            super().paint(painter, option, index)
            return
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(theme.TINT))
        valor = index.data(ROLE_BRUTO)
        spec = col.pilula(valor)
        painter.save()
        painter.setPen(QColor(theme.LINE_SOFT))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        if spec:
            texto, cor, fundo = spec
            fonte = QFont(theme.SANS)
            fonte.setPixelSize(11)
            fonte.setWeight(QFont.Weight.Medium)
            painter.setFont(fonte)
            largura = painter.fontMetrics().horizontalAdvance(texto) + 20
            altura = 22
            x = option.rect.x() + 8
            if col.alinhamento == "centro":
                x = option.rect.center().x() - largura / 2
            y = option.rect.center().y() - altura / 2
            r = QRectF(x, y, largura, altura)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(fundo))
            painter.drawRoundedRect(r, 11, 11)
            painter.setPen(QColor(cor))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, texto)
        painter.restore()


def criar_tabela(colunas: list[Coluna], altura_linha: int = 42) -> tuple[QTableView, ModeloTabela, Ordenador]:
    modelo = ModeloTabela(colunas)
    proxy = Ordenador()
    proxy.setSourceModel(modelo)
    tabela = QTableView()
    tabela.setModel(proxy)
    tabela.setItemDelegate(DelegadoPilula(modelo, tabela))
    tabela.setSortingEnabled(True)
    tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tabela.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tabela.setShowGrid(False)
    tabela.setWordWrap(False)
    tabela.verticalHeader().setVisible(False)
    tabela.verticalHeader().setDefaultSectionSize(altura_linha)
    tabela.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    tabela.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    tabela.setFrameShape(QFrame.Shape.NoFrame)
    cab = tabela.horizontalHeader()
    cab.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
    proxy.sort(-1)
    cab.setHighlightSections(False)
    cab.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    cab.setMinimumSectionSize(48)
    for i, col in enumerate(colunas):
        if col.esticar:
            cab.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        else:
            cab.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            if col.largura:
                tabela.setColumnWidth(i, col.largura)
    return tabela, modelo, proxy


def linhas_selecionadas(tabela: QTableView, modelo: ModeloTabela, proxy: Ordenador) -> list[Any]:
    linhas = sorted({i.row() for i in tabela.selectionModel().selectedRows()})
    return [modelo.linha(proxy.mapToSource(proxy.index(r, 0)).row()) for r in linhas]


def linha_do_indice(indice, modelo: ModeloTabela, proxy: Ordenador) -> Any:
    return modelo.linha(proxy.mapToSource(indice).row())


def pilula_nivel(nivel: str):
    cor, fundo, texto = theme.NIVEL_CORES.get(nivel, (theme.MUTED, theme.GREY_SOFT, nivel))
    return texto, cor, fundo
