"""Chave de acesso da NF-e/NFC-e (44 dígitos).

Estrutura: cUF(2) AAMM(4) CNPJ/CPF(14) mod(2) serie(3) nNF(9) tpEmis(1) cNF(8) cDV(1)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SO_DIGITOS = re.compile(r"\D")


def somente_digitos(texto: str | None) -> str:
    return _SO_DIGITOS.sub("", texto or "")


def calcular_dv(chave43: str) -> int:
    """Dígito verificador módulo 11 (pesos 2 a 9, da direita para a esquerda)."""
    soma = 0
    peso = 2
    for digito in reversed(chave43):
        soma += int(digito) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def chave_valida(chave: str) -> bool:
    chave = somente_digitos(chave)
    if len(chave) != 44:
        return False
    return calcular_dv(chave[:43]) == int(chave[43])


@dataclass(frozen=True)
class PartesChave:
    cuf: str
    ano_mes: str  # AAAA-MM
    cnpj: str
    modelo: str
    serie: int
    numero: int
    tp_emis: str


def decompor(chave: str) -> PartesChave | None:
    chave = somente_digitos(chave)
    if len(chave) != 44:
        return None
    aamm = chave[2:6]
    return PartesChave(
        cuf=chave[0:2],
        ano_mes=f"20{aamm[:2]}-{aamm[2:]}",
        cnpj=chave[6:20],
        modelo=chave[20:22],
        serie=int(chave[22:25]),
        numero=int(chave[25:34]),
        tp_emis=chave[34],
    )


def formatar_cnpj(doc: str | None) -> str:
    d = somente_digitos(doc)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return d


def cnpj_valido(cnpj: str) -> bool:
    d = somente_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False

    def dv(base: str, pesos: list[int]) -> int:
        s = sum(int(a) * b for a, b in zip(base, pesos))
        r = s % 11
        return 0 if r < 2 else 11 - r

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6] + p1
    return dv(d[:12], p1) == int(d[12]) and dv(d[:13], p2) == int(d[13])
