"""Identidade visual: cores, fontes e folha de estilos (QSS)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

from conferi.core.config import pasta_dados

FONTES = Path(__file__).resolve().parents[1] / "assets" / "fonts"

NAVY = "#16233A"
NAVY_2 = "#22344F"
NAVY_3 = "#2B3D5C"
GOLD = "#B08A4A"
GOLD_SOFT = "#F7F0E3"
PAPER = "#F6F3ED"
CARD = "#FFFFFF"
LINE = "#E7E1D6"
LINE_SOFT = "#F0ECE4"
INK = "#1B2230"
MUTED = "#6B7385"
TINT = "#EEF1F5"
RED = "#B4473A"
RED_SOFT = "#F7E4E1"
AMBER = "#B7832F"
AMBER_SOFT = "#F7EEDC"
BLUE = "#3D5A80"
BLUE_SOFT = "#E8EDF4"
GREEN = "#2F7D5B"
GREEN_SOFT = "#E7F1EC"
GREY_SOFT = "#EFEDE8"

SERIF = "Lora"
SANS = "Poppins"
BODY = "Carlito"

NIVEL_CORES = {
    "alta": (RED, RED_SOFT, "Alta"),
    "media": (AMBER, AMBER_SOFT, "Média"),
    "baixa": (BLUE, BLUE_SOFT, "Baixa"),
    "info": (MUTED, GREY_SOFT, "Info"),
}


def carregar_fontes() -> None:
    global SERIF, SANS, BODY
    familias = {}
    for arquivo in sorted(FONTES.glob("*.ttf")):
        ident = QFontDatabase.addApplicationFont(str(arquivo))
        if ident >= 0:
            for familia in QFontDatabase.applicationFontFamilies(ident):
                familias[arquivo.stem.split("-")[0]] = familia
    SERIF = familias.get("Lora", "Georgia")
    SANS = familias.get("Poppins", "Segoe UI")
    BODY = familias.get("Carlito", "Calibri")


def _icone_check() -> str:
    pasta = pasta_dados() / "ui"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "check.svg"
    if not arquivo.exists():
        arquivo.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" '
            'stroke="white" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M5 12.5l4.5 4.5L19 7.5"/></svg>', encoding="utf-8")
    return arquivo.as_posix()


def _icone_seta() -> str:
    pasta = pasta_dados() / "ui"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "seta.svg"
    if not arquivo.exists():
        arquivo.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" '
            f'stroke="{MUTED}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M6 9l6 6 6-6"/></svg>', encoding="utf-8")
    return arquivo.as_posix()


def folha_de_estilos() -> str:
    check = _icone_check()
    seta = _icone_seta()
    return f"""
    * {{ outline: 0; }}
    QWidget {{ font-family: "{BODY}"; font-size: 14px; color: {INK}; }}
    QMainWindow, QDialog, #Content, #PageBody {{ background: {PAPER}; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}

    #Sidebar {{ background: {NAVY}; }}
    #Sidebar QLabel {{ color: #C9D1DD; background: transparent; }}
    #SidebarBrand {{ font-family: "{SERIF}"; font-size: 24px; color: white; }}
    #SidebarBrandAI {{ font-family: "{SANS}"; font-size: 13px; color: {GOLD}; font-weight: 500; }}
    #SidebarFootTitle {{ font-family: "{SANS}"; font-size: 11px; color: white; font-weight: 500; }}
    #SidebarFoot {{ font-size: 12.5px; color: #9AA6B8; }}
    #SidebarDivider {{ background: {NAVY_3}; max-height: 1px; min-height: 1px; }}
    #NavItem {{ background: transparent; border: none; border-radius: 9px; text-align: left; padding: 0; }}
    #NavItem:hover {{ background: rgba(255,255,255,0.06); }}
    #NavItem:checked {{ background: rgba(176,138,74,0.18); }}
    #NavText {{ font-family: "{SANS}"; font-size: 13px; color: #AEB8C8; font-weight: 500; }}
    #NavItem:checked #NavText {{ color: white; }}
    #NavBadge {{ background: {RED}; color: white; font-family: "{SANS}"; font-size: 10px; font-weight: 600;
                 border-radius: 9px; padding: 1px 7px; }}
    #NavMarker {{ background: transparent; border-radius: 2px; }}
    #NavItem:checked #NavMarker {{ background: {GOLD}; }}

    #Card {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 12px; }}
    #CardFlat {{ background: transparent; border: none; }}
    #Dropzone {{ background: {CARD}; border: 2px dashed #D3CBBC; border-radius: 16px; }}
    #Dropzone[ativo="true"] {{ border-color: {GOLD}; background: {GOLD_SOFT}; }}
    #Banner {{ background: {GOLD_SOFT}; border: none; border-left: 3px solid {GOLD}; border-radius: 6px; }}
    #BannerInfo {{ background: {TINT}; border: none; border-left: 3px solid {NAVY}; border-radius: 6px; }}
    #BannerErro {{ background: {RED_SOFT}; border: none; border-left: 3px solid {RED}; border-radius: 6px; }}

    QLabel {{ background: transparent; }}
    QLabel#Kicker {{ font-family: "{SANS}"; font-size: 11px; color: {GOLD}; font-weight: 500; }}
    QLabel#PageTitle {{ font-family: "{SERIF}"; font-size: 30px; color: {NAVY}; }}
    QLabel#PageSubtitle {{ font-size: 14px; color: {MUTED}; }}
    QLabel#CardTitle {{ font-family: "{SERIF}"; font-size: 18px; color: {NAVY}; }}
    QLabel#SectionLabel {{ font-family: "{SANS}"; font-size: 10.5px; color: {MUTED}; font-weight: 500;
                           }}
    QLabel#Muted {{ color: {MUTED}; }}
    QLabel#Small {{ font-size: 12.5px; color: {MUTED}; }}
    QLabel#KpiLabel {{ font-family: "{SANS}"; font-size: 10.5px; color: {MUTED}; font-weight: 500; }}
    QLabel#KpiValue {{ font-family: "{SERIF}"; font-size: 30px; color: {NAVY}; }}
    QLabel#KpiSub {{ font-size: 13px; color: {MUTED}; }}
    QLabel#EmptyTitle {{ font-family: "{SERIF}"; font-size: 22px; color: {NAVY}; }}
    QLabel#Link {{ font-family: "{SANS}"; font-size: 11.5px; color: {GOLD}; font-weight: 500; }}

    QPushButton {{ font-family: "{SANS}"; font-size: 12px; font-weight: 500; border-radius: 8px; padding: 9px 16px;
                   border: 1px solid {NAVY}; color: {NAVY}; background: transparent; }}
    QPushButton:hover {{ background: {TINT}; }}
    QPushButton:pressed {{ background: #E1E6EE; }}
    QPushButton#Primary {{ background: {NAVY}; color: white; }}
    QPushButton#Primary:hover {{ background: {NAVY_2}; }}
    QPushButton#Gold {{ background: {GOLD}; border-color: {GOLD}; color: white; }}
    QPushButton#Gold:hover {{ background: #9E7B40; }}
    QPushButton#Ghost {{ border: 1px solid {LINE}; background: white; color: {NAVY}; }}
    QPushButton#Ghost:hover {{ border-color: #CFC7B8; }}
    QPushButton#Danger {{ border: 1px solid {RED}; color: {RED}; background: white; }}
    QPushButton#Text {{ border: none; color: {GOLD}; padding: 4px 2px; background: transparent; }}
    QPushButton#Text:hover {{ color: #8E6E39; }}
    QPushButton:disabled {{ color: #A3AAB8; border-color: {LINE}; background: #F3F1EC; }}
    QPushButton#Chip {{ border-radius: 15px; padding: 6px 14px; border: 1px solid {LINE}; background: white;
                        color: {MUTED}; font-size: 11.5px; }}
    QPushButton#Chip:hover {{ border-color: #CFC7B8; }}
    QPushButton#Chip:checked {{ background: {NAVY}; border-color: {NAVY}; color: white; }}

    QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit {{
        background: white; border: 1px solid {LINE}; border-radius: 8px; padding: 7px 10px;
        font-family: "{SANS}"; font-size: 12px; color: {NAVY}; min-height: 18px; }}
    QComboBox:hover, QLineEdit:hover {{ border-color: #CFC7B8; }}
    QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
    QPlainTextEdit:focus {{ border-color: {GOLD}; }}
    QComboBox::drop-down {{ border: none; width: 26px; }}
    QComboBox::down-arrow {{ image: url("{seta}"); width: 12px; height: 12px; }}
    QComboBox QAbstractItemView {{ background: white; border: 1px solid {LINE}; selection-background-color: {TINT};
                                   selection-color: {NAVY}; padding: 4px; }}
    QLineEdit[readOnly="true"] {{ background: #FAF8F4; color: {MUTED}; }}

    QTableView {{ background: white; border: none; gridline-color: transparent; selection-background-color: {TINT};
                  selection-color: {INK}; font-size: 13.5px; }}
    QTableView::item {{ padding: 0 8px; border-bottom: 1px solid {LINE_SOFT}; }}
    QTableView::item:selected {{ background: {TINT}; color: {INK}; }}
    QHeaderView {{ background: white; border: none; }}
    QHeaderView::section {{ background: white; color: {MUTED}; font-family: "{SANS}"; font-size: 10.5px;
                            font-weight: 500; padding: 9px 8px; border: none; border-bottom: 1px solid {LINE}; }}
    QTableCornerButton::section {{ background: white; border: none; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: #D6D0C4; border-radius: 4px; min-height: 30px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: #D6D0C4; border-radius: 4px; min-width: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QProgressBar {{ background: #EFEAE1; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; }}
    QProgressBar::chunk {{ background: {GOLD}; border-radius: 4px; }}

    QTabWidget::pane {{ border: none; border-top: 1px solid {LINE}; top: -1px; }}
    QTabBar::tab {{ font-family: "{SANS}"; font-size: 12px; padding: 9px 16px; color: {MUTED}; background: transparent;
                    border: none; border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ color: {NAVY}; border-bottom: 2px solid {GOLD}; }}
    QTabBar::tab:hover {{ color: {NAVY}; }}

    QCheckBox {{ font-size: 13.5px; spacing: 8px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid #C2C9D4; border-radius: 4px; background: white; }}
    QCheckBox::indicator:checked {{ background: {NAVY}; border-color: {NAVY}; image: url("{check}"); }}

    QToolTip {{ background: {NAVY}; color: white; border: none; padding: 6px 8px; font-size: 12.5px; }}
    QMessageBox QLabel {{ font-size: 14px; }}
    QMenu {{ background: white; border: 1px solid {LINE}; padding: 4px; }}
    QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {TINT}; color: {NAVY}; }}
    """
