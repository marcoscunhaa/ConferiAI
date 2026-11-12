"""Ícones vetoriais (traço fino, 24×24) desenhados a partir de SVG embutido."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

CAMINHOS = {
    "painel": '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/>'
              '<rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    "importar": '<path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M4 19h16"/>',
    "clientes": '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M17 4a4 4 0 0 1 0 8"/>'
                '<path d="M22 21a7 7 0 0 0-4-6.3"/>',
    "notas": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'
             '<path d="M9 13h6"/><path d="M9 17h6"/>',
    "pendencias": '<path d="M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0z"/>'
                  '<path d="M12 9v4"/><path d="M12 17h.01"/>',
    "sefaz": '<path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "relatorios": '<path d="M3 21h18"/><path d="M6 21V10"/><path d="M11 21V4"/><path d="M16 21v-7"/><path d="M21 21V8"/>',
    "config": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3'
              'M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "pasta": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "arquivo": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "upload": '<path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 20h16"/>',
    "nuvem": '<path d="M7 18a5 5 0 1 1 .9-9.9A6 6 0 0 1 19 10a4 4 0 0 1-1 7.9z"/><path d="M12 12v6"/>'
             '<path d="M9.5 14.5L12 12l2.5 2.5"/>',
    "busca": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "check_circulo": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.8 2.8L16.5 9.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "alerta": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5"/><path d="M12 16.5h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.5h.01"/>',
    "excel": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8l8 8M16 8l-8 8"/>',
    "pdf": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'
           '<path d="M8.5 15.5h7"/><path d="M8.5 12h4"/>',
    "backup": '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.5"/><path d="M4.5 5.5v6c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-6"/>'
              '<path d="M4.5 11.5v6c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-6"/>',
    "restaurar": '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/>',
    "atualizar": '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
    "seta_direita": '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>',
    "copiar": '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
    "olho": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "escudo": '<path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z"/>',
    "calendario": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
    "camadas": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    "faisca": '<path d="M12 3l1.8 5.4L19 10l-5.2 1.6L12 17l-1.8-5.4L5 10l5.2-1.6z"/><path d="M19 17l.7 2 2 .7-2 .7-.7 2'
              '-.7-2-2-.7 2-.7z"/>',
}


@lru_cache(maxsize=256)
def pixmap(nome: str, cor: str = "#16233A", tamanho: int = 18, espessura: float = 1.7) -> QPixmap:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{cor}" '
           f'stroke-width="{espessura}" stroke-linecap="round" stroke-linejoin="round">{CAMINHOS.get(nome, "")}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    escala = 2
    pm = QPixmap(tamanho * escala, tamanho * escala)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, tamanho * escala, tamanho * escala))
    painter.end()
    pm.setDevicePixelRatio(escala)
    return pm


def icone(nome: str, cor: str = "#16233A", tamanho: int = 18) -> QIcon:
    return QIcon(pixmap(nome, cor, tamanho))
