"""Valores monetários.

Valores são guardados no banco como inteiros em centavos, para que somas no SQLite
sejam exatas. Conversões passam sempre por Decimal.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")


def to_decimal(texto: str | None) -> Decimal:
    """Converte o texto de um campo numérico do XML (ponto decimal) em Decimal."""
    if texto is None:
        return Decimal("0")
    texto = texto.strip()
    if not texto:
        return Decimal("0")
    try:
        return Decimal(texto)
    except InvalidOperation:
        # Alguns emissores mandam vírgula decimal, fora do padrão.
        try:
            return Decimal(texto.replace(".", "").replace(",", "."))
        except InvalidOperation:
            return Decimal("0")


def to_cents(texto: str | None) -> int:
    """Texto do XML -> centavos (inteiro), com arredondamento comercial."""
    valor = to_decimal(texto).quantize(CENT, rounding=ROUND_HALF_UP)
    return int(valor * 100)


def cents_to_decimal(centavos: int | None) -> Decimal:
    return (Decimal(centavos or 0) / 100).quantize(CENT)


def fmt_brl(centavos: int | None, simbolo: bool = True) -> str:
    """Formata centavos como moeda brasileira: R$ 1.234,56."""
    valor = cents_to_decimal(centavos)
    negativo = valor < 0
    inteiro, _, frac = f"{abs(valor):.2f}".partition(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    texto = f"{'.'.join(grupos)},{frac}"
    if negativo:
        texto = "-" + texto
    return f"R$ {texto}" if simbolo else texto


def fmt_brl_curto(centavos: int | None) -> str:
    """Formato compacto para cartões: R$ 18,4 mi / R$ 512 mil / R$ 980,00."""
    valor = cents_to_decimal(centavos)
    a = abs(valor)
    sinal = "-" if valor < 0 else ""
    if a >= 1_000_000:
        return f"{sinal}R$ {str(round(a / 1_000_000, 1)).replace('.', ',')} mi"
    if a >= 10_000:
        return f"{sinal}R$ {int(round(a / 1000))} mil"
    return fmt_brl(centavos)
