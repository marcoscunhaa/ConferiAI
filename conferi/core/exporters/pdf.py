"""Relatório de pendências em PDF (ReportLab)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..chave import formatar_cnpj
from ..consultas import FiltroPendencias, listar_pendencias, rotulo_periodo
from ..rules import NIVEL_ROTULO, REGRAS

FONTES = Path(__file__).resolve().parents[2] / "assets" / "fonts"
NAVY = colors.HexColor("#16233A")
GOLD = colors.HexColor("#B08A4A")
PAPER = colors.HexColor("#F7F4EE")
LINE = colors.HexColor("#DCD6CA")
MUTED = colors.HexColor("#5E6675")
COR_NIVEL = {"alta": "#A4483A", "media": "#94692A", "baixa": "#3D5A80", "info": "#5E6675"}

_fontes_ok: tuple[str, str, str] | None = None


def _fontes() -> tuple[str, str, str]:
    """Registra as fontes do aplicativo; usa Helvetica se não estiverem disponíveis."""
    global _fontes_ok
    if _fontes_ok:
        return _fontes_ok
    try:
        pdfmetrics.registerFont(TTFont("CAI-Serif", str(FONTES / "Lora-Variable.ttf")))
        pdfmetrics.registerFont(TTFont("CAI-Body", str(FONTES / "Carlito-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("CAI-Bold", str(FONTES / "Carlito-Bold.ttf")))
        pdfmetrics.registerFontFamily("CAI-Body", normal="CAI-Body", bold="CAI-Bold")
        _fontes_ok = ("CAI-Serif", "CAI-Body", "CAI-Bold")
    except Exception:  # noqa: BLE001 — qualquer falha de fonte cai no padrão
        _fontes_ok = ("Helvetica-Bold", "Helvetica", "Helvetica-Bold")
    return _fontes_ok


def exportar_pendencias(con: sqlite3.Connection, destino: str | Path, filtro: FiltroPendencias,
                        nome_cliente: str = "") -> Path:
    destino = Path(destino)
    serif, corpo, negrito = _fontes()
    pend = listar_pendencias(con, filtro)

    s_cel = ParagraphStyle("cel", fontName=corpo, fontSize=8.6, leading=11, textColor=colors.HexColor("#1B2230"))
    s_cab = ParagraphStyle("cab", fontName=negrito, fontSize=8, leading=10, textColor=colors.white)
    s_tit = ParagraphStyle("tit", fontName=serif, fontSize=20, leading=24, textColor=NAVY)
    s_sub = ParagraphStyle("sub", fontName=corpo, fontSize=10, leading=13, textColor=MUTED)
    s_nota = ParagraphStyle("nota", fontName=corpo, fontSize=8.4, leading=11, textColor=MUTED)

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, doc.pagesize[1] - 0.25 * cm, doc.pagesize[0], 0.25 * cm, stroke=0, fill=1)
        canvas.setFont(corpo, 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(1.5 * cm, 0.9 * cm, "Conferi AI · alertas para conferência; a decisão fiscal é do profissional "
                                                "responsável.")
        canvas.drawRightString(doc.pagesize[0] - 1.5 * cm, 0.9 * cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(destino), pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.6 * cm, title="Relatório de pendências — Conferi AI",
                            author="Conferi AI")
    largura = landscape(A4)[0] - 3 * cm

    escopo = nome_cliente or "Todos os clientes"
    historia = [
        Paragraph("Relatório de pendências", s_tit),
        Paragraph(f"{escape(escopo)} · {rotulo_periodo(filtro.ano_mes)} · gerado em {datetime.now():%d/%m/%Y às %H:%M}",
                  s_sub),
        Spacer(1, 10),
    ]

    contagem = {n: sum(1 for p in pend if p["nivel"] == n) for n in ("alta", "media", "baixa", "info")}
    cartoes = [[Paragraph(f'<font name="{negrito}" size="7.5" color="#5E6675">{rot.upper()}</font>', s_cel)
                for rot in ("Pendências", "Alta", "Média", "Baixa")],
               [Paragraph(f'<font name="{serif}" size="18" color="{cor}">{valor}</font>', s_cel)
                for valor, cor in ((len(pend), "#16233A"), (contagem["alta"], COR_NIVEL["alta"]),
                                   (contagem["media"], COR_NIVEL["media"]), (contagem["baixa"], COR_NIVEL["baixa"]))]]
    t = Table(cartoes, colWidths=[largura / 4] * 4)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PAPER), ("LINEABOVE", (0, 0), (-1, 0), 1.4, GOLD),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, -1), (-1, -1), 8)]))
    historia += [t, Spacer(1, 14)]

    if not pend:
        historia.append(Paragraph("Nenhuma pendência encontrada com os filtros selecionados.", s_sub))
    else:
        linhas = [[Paragraph(x, s_cab) for x in ("Nível", "Cliente", "Documento", "Data", "Regra", "Alerta", "Detalhe")]]
        for p in pend:
            doc_txt = "—"
            if p["numero"]:
                doc_txt = f"{'NFC-e' if p['modelo'] == '65' else 'NF-e'} {p['numero']} / {p['serie']}"
            data = p["data_ref"]
            data_txt = f"{data[8:10]}/{data[5:7]}/{data[:4]}" if len(data) >= 10 else data
            linhas.append([
                Paragraph(f'<font name="{negrito}" color="{COR_NIVEL.get(p["nivel"], "#1B2230")}">'
                          f'{NIVEL_ROTULO.get(p["nivel"], p["nivel"])}</font>', s_cel),
                Paragraph(f'{escape(p["empresa_nome"] or "")}<br/><font color="#5E6675" size="7.5">'
                          f'{formatar_cnpj(p["cnpj_empresa"])}</font>', s_cel),
                Paragraph(doc_txt, s_cel),
                Paragraph(data_txt, s_cel),
                Paragraph(REGRAS.get(p["regra"], p["regra"]), s_cel),
                Paragraph(f'<b>{escape(p["titulo"])}</b>', s_cel),
                Paragraph(escape(p["detalhe"] or ""), s_cel),
            ])
        pesos = [1.6, 4.6, 2.6, 1.9, 2.8, 5.6, 7.4]
        total = sum(pesos)
        tabela = Table(linhas, colWidths=[largura * x / total for x in pesos], repeatRows=1)
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
        ]))
        historia.append(tabela)
    historia += [Spacer(1, 10), Paragraph(
        "Os alertas apontam pontos para conferência a partir dos XMLs importados. Regras fiscais em transição "
        "(como IBS/CBS) devem ser confirmadas nas normas vigentes.", s_nota)]
    doc.build(historia, onFirstPage=rodape, onLaterPages=rodape)
    return destino
