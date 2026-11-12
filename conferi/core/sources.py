"""Fontes de entrada de documentos.

A origem das notas é um módulo plugável: hoje existe a fonte de pastas e arquivos .zip.
Fontes futuras (captura pela Sefaz, ambiente nacional) só precisam implementar
`FonteDocumentos`.
"""

from __future__ import annotations

import os
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

LIMITE_MEMBRO_ZIP = 30 * 1024 * 1024        # 30 MB por XML dentro do .zip
LIMITE_TOTAL_ZIP = 4 * 1024 * 1024 * 1024    # 4 GB descompactados por .zip
LIMITE_ARQUIVOS_ZIP = 500_000


@dataclass
class ArquivoEntrada:
    nome: str                       # caminho exibido ao usuário
    ler: Callable[[], bytes]        # carrega o conteúdo sob demanda
    erro: str | None = None         # problema detectado antes da leitura


class FonteDocumentos(Protocol):
    descricao: str

    def contar(self) -> int: ...

    def arquivos(self) -> Iterator[ArquivoEntrada]: ...


def _e_xml(nome: str) -> bool:
    return nome.lower().endswith(".xml")


def _e_zip(nome: str) -> bool:
    return nome.lower().endswith(".zip")


class FontePastasArquivos:
    """Lê XMLs de pastas (recursivamente), arquivos XML soltos e arquivos .zip."""

    def __init__(self, caminhos: list[str | Path]):
        self.caminhos = [Path(c) for c in caminhos]
        nomes = ", ".join(p.name for p in self.caminhos[:3])
        self.descricao = nomes + ("…" if len(self.caminhos) > 3 else "")

    def _arquivos_fisicos(self) -> Iterator[Path]:
        for caminho in self.caminhos:
            if caminho.is_dir():
                for raiz, _dirs, arquivos in os.walk(caminho):
                    for nome in sorted(arquivos):
                        if _e_xml(nome) or _e_zip(nome):
                            yield Path(raiz) / nome
            elif caminho.is_file() and (_e_xml(caminho.name) or _e_zip(caminho.name)):
                yield caminho

    def contar(self) -> int:
        total = 0
        for arquivo in self._arquivos_fisicos():
            if _e_zip(arquivo.name):
                try:
                    with zipfile.ZipFile(arquivo) as z:
                        total += sum(1 for i in z.infolist() if _e_xml(i.filename) and not i.is_dir())
                except (zipfile.BadZipFile, OSError):
                    total += 1
            else:
                total += 1
        return total

    def arquivos(self) -> Iterator[ArquivoEntrada]:
        for arquivo in self._arquivos_fisicos():
            if _e_zip(arquivo.name):
                yield from self._membros_zip(arquivo)
            else:
                yield ArquivoEntrada(str(arquivo), arquivo.read_bytes)

    def _membros_zip(self, arquivo: Path) -> Iterator[ArquivoEntrada]:
        try:
            z = zipfile.ZipFile(arquivo)
        except (zipfile.BadZipFile, OSError) as erro:
            yield ArquivoEntrada(str(arquivo), lambda: b"", erro=f".zip corrompido ou ilegível ({erro})")
            return
        with z:
            membros = [i for i in z.infolist() if _e_xml(i.filename) and not i.is_dir()]
            if len(membros) > LIMITE_ARQUIVOS_ZIP:
                yield ArquivoEntrada(str(arquivo), lambda: b"", erro="o .zip tem arquivos demais")
                return
            total = 0
            for info in membros:
                nome = f"{arquivo}::{info.filename}"
                total += info.file_size
                if info.file_size > LIMITE_MEMBRO_ZIP:
                    yield ArquivoEntrada(nome, lambda: b"", erro="arquivo dentro do .zip maior que 30 MB")
                    continue
                if total > LIMITE_TOTAL_ZIP:
                    yield ArquivoEntrada(nome, lambda: b"", erro="conteúdo descompactado do .zip excede o limite")
                    return
                try:
                    dados = z.read(info)
                except (zipfile.BadZipFile, OSError, RuntimeError) as erro:
                    yield ArquivoEntrada(nome, lambda: b"", erro=f"não foi possível extrair ({erro})")
                    continue
                yield ArquivoEntrada(nome, lambda d=dados: d)
