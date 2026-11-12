"""Conferência entre as notas recebidas do cliente e a relação de notas da Sefaz.

O arquivo da Sefaz pode ser CSV, TXT ou XLSX exportado do portal. Como cada portal
exporta num layout diferente, a leitura é tolerante: procura chaves de acesso
(44 dígitos, com ou sem espaços) em cada linha e identifica a situação por palavras
como "cancelada", "denegada" ou "autorizada".
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .chave import chave_valida, decompor, somente_digitos

PADRAO_CHAVE = re.compile(r"(?<!\d)(\d{4}(?:[ .\-]?\d{4}){10})(?!\d)")


@dataclass
class RegistroSefaz:
    chave: str
    situacao: str  # autorizada | cancelada | denegada | desconhecida
    linha: int


@dataclass
class LeituraSefaz:
    registros: list[RegistroSefaz] = field(default_factory=list)
    linhas_lidas: int = 0
    chaves_invalidas: int = 0
    avisos: list[str] = field(default_factory=list)


def _situacao(texto: str) -> str:
    t = texto.lower()
    if "cancel" in t:
        return "cancelada"
    if "deneg" in t:
        return "denegada"
    if "autoriz" in t or "normal" in t or "emitid" in t or "ativa" in t:
        return "autorizada"
    return "desconhecida"


def _linhas_do_arquivo(caminho: Path) -> list[str]:
    sufixo = caminho.suffix.lower()
    if sufixo in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        wb = load_workbook(caminho, read_only=True, data_only=True)
        linhas = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                celulas = []
                for c in row:
                    if c is None:
                        continue
                    if isinstance(c, float) and c.is_integer():
                        c = int(c)
                    celulas.append(str(c))
                linhas.append(" ; ".join(celulas))
        wb.close()
        return linhas

    bruto = caminho.read_bytes()
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    if sufixo == ".csv":
        try:
            dialeto = csv.Sniffer().sniff(texto[:4096], delimiters=";,\t|")
            return [" ; ".join(r) for r in csv.reader(io.StringIO(texto), dialeto)]
        except csv.Error:
            pass
    return texto.splitlines()


def ler_arquivo_sefaz(caminho: str | Path) -> LeituraSefaz:
    caminho = Path(caminho)
    leitura = LeituraSefaz()
    vistos: dict[str, RegistroSefaz] = {}
    for numero, linha in enumerate(_linhas_do_arquivo(caminho), start=1):
        leitura.linhas_lidas += 1
        for achado in PADRAO_CHAVE.findall(linha):
            chave = somente_digitos(achado)
            if not chave_valida(chave):
                leitura.chaves_invalidas += 1
                continue
            situacao = _situacao(linha)
            anterior = vistos.get(chave)
            # Se a mesma chave aparece duas vezes, "cancelada" prevalece.
            if anterior is None or situacao == "cancelada":
                vistos[chave] = RegistroSefaz(chave, situacao, numero)
    leitura.registros = list(vistos.values())
    if not leitura.registros:
        leitura.avisos.append("Nenhuma chave de acesso válida foi encontrada no arquivo.")
    elif all(r.situacao == "desconhecida" for r in leitura.registros):
        leitura.avisos.append("O arquivo não informa a situação das notas; todas foram tratadas como autorizadas.")
        for r in leitura.registros:
            r.situacao = "autorizada"
    return leitura


@dataclass
class LinhaConferencia:
    chave: str
    modelo: str
    serie: int
    numero: int
    data: str
    valor: int | None
    situacao_sefaz: str
    situacao_escritorio: str


@dataclass
class ResultadoConferencia:
    cnpj: str
    ano_mes: str
    conferem: list[LinhaConferencia] = field(default_factory=list)
    faltando_no_escritorio: list[LinhaConferencia] = field(default_factory=list)
    fora_da_sefaz: list[LinhaConferencia] = field(default_factory=list)
    cancelada_na_sefaz: list[LinhaConferencia] = field(default_factory=list)
    cancelada_no_escritorio: list[LinhaConferencia] = field(default_factory=list)
    registros_outros_periodos: int = 0

    @property
    def total_divergencias(self) -> int:
        return (len(self.faltando_no_escritorio) + len(self.fora_da_sefaz)
                + len(self.cancelada_na_sefaz) + len(self.cancelada_no_escritorio))


def conferir(con: sqlite3.Connection, cnpj: str, ano_mes: str, leitura: LeituraSefaz,
             modelos: set[str] | None = None) -> ResultadoConferencia:
    """Compara as notas emitidas pelo cliente no mês com a relação da Sefaz."""
    res = ResultadoConferencia(cnpj=cnpj, ano_mes=ano_mes)
    sefaz: dict[str, RegistroSefaz] = {}
    for r in leitura.registros:
        partes = decompor(r.chave)
        if partes and partes.cnpj == cnpj and partes.ano_mes == ano_mes and (not modelos or partes.modelo in modelos):
            sefaz[r.chave] = r
        else:
            res.registros_outros_periodos += 1

    modelos_considerados = modelos or {decompor(c).modelo for c in sefaz} or {"55", "65"}
    marcadores = ",".join("?" * len(modelos_considerados))
    locais = {
        r["chave"]: r for r in con.execute(
            f"SELECT chave, modelo, serie, numero, data_emissao, v_nf, cancelada FROM notas "
            f"WHERE emit_doc = ? AND ano_mes = ? AND tp_amb = 1 AND modelo IN ({marcadores})",
            (cnpj, ano_mes, *sorted(modelos_considerados)),
        )
    }

    for chave in sorted(set(sefaz) | set(locais)):
        reg, loc = sefaz.get(chave), locais.get(chave)
        partes = decompor(chave)
        linha = LinhaConferencia(
            chave=chave, modelo=partes.modelo, serie=partes.serie, numero=partes.numero,
            data=loc["data_emissao"] if loc else "", valor=loc["v_nf"] if loc else None,
            situacao_sefaz=reg.situacao if reg else "não consta",
            situacao_escritorio=("cancelada" if loc["cancelada"] else "ativa") if loc else "não recebida",
        )
        if reg and not loc:
            if reg.situacao == "cancelada":
                res.conferem.append(linha)  # cancelada e não recebida: nada a lançar
            else:
                res.faltando_no_escritorio.append(linha)
        elif loc and not reg:
            res.fora_da_sefaz.append(linha)
        elif reg.situacao == "cancelada" and not loc["cancelada"]:
            res.cancelada_na_sefaz.append(linha)
        elif reg.situacao in ("autorizada",) and loc["cancelada"]:
            res.cancelada_no_escritorio.append(linha)
        else:
            res.conferem.append(linha)
    for lista in (res.faltando_no_escritorio, res.fora_da_sefaz, res.cancelada_na_sefaz,
                  res.cancelada_no_escritorio, res.conferem):
        lista.sort(key=lambda x: (x.modelo, x.serie, x.numero))
    return res
