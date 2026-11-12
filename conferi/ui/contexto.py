"""Estado compartilhado da aplicação e execução de tarefas em segundo plano."""

from __future__ import annotations

import sqlite3
import threading
import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from conferi.core.chave import formatar_cnpj
from conferi.core.servico import Ambiente


class Contexto(QObject):
    """Mantém o ambiente, a conexão da thread principal e avisa as telas quando os dados mudam."""

    dados_alterados = Signal()
    navegar = Signal(str, dict)      # nome da página, filtros

    def __init__(self, ambiente: Ambiente):
        super().__init__()
        self.ambiente = ambiente
        self.con: sqlite3.Connection = ambiente.conectar()
        self._tarefas: list[tuple[QThread, QObject, QObject]] = []

    def reconectar(self) -> None:
        try:
            self.con.close()
        except sqlite3.Error:
            pass
        self.con = self.ambiente.conectar()

    def fechar(self) -> None:
        try:
            self.con.close()
        except sqlite3.Error:
            pass

    def avisar_alteracao(self) -> None:
        self.dados_alterados.emit()

    # ------------------------------------------------------------- segundo plano
    def executar(self, funcao: Callable[[], Any], ao_concluir: Callable[[Any], None] | None = None,
                 ao_falhar: Callable[[str], None] | None = None) -> None:
        """Roda `funcao` numa thread separada. A função deve abrir a própria conexão."""
        thread = QThread()
        trabalhador = _Trabalhador(funcao)
        trabalhador.moveToThread(thread)
        # O retransmissor vive na thread principal: os callbacks (que mexem na interface) rodam nela.
        retransmissor = _Retransmissor(ao_concluir, ao_falhar, self)
        thread.started.connect(trabalhador.rodar)
        trabalhador.concluido.connect(retransmissor.ok)
        trabalhador.falhou.connect(retransmissor.erro)
        trabalhador.finalizado.connect(thread.quit)
        thread.finished.connect(retransmissor.terminou)
        retransmissor.liberar.connect(self._liberar)
        self._tarefas.append((thread, trabalhador, retransmissor))
        thread.start()

    @Slot(object)
    def _liberar(self, retransmissor: QObject) -> None:
        restantes = []
        for t, w, r in self._tarefas:
            if r is retransmissor:
                t.deleteLater()
                w.deleteLater()
                r.deleteLater()
            else:
                restantes.append((t, w, r))
        self._tarefas = restantes

    def tarefas_ativas(self) -> bool:
        return bool(self._tarefas)


class _Retransmissor(QObject):
    liberar = Signal(object)

    def __init__(self, ao_concluir, ao_falhar, parent: QObject):
        super().__init__(parent)
        self._ao_concluir = ao_concluir
        self._ao_falhar = ao_falhar

    @Slot(object)
    def ok(self, resultado: Any) -> None:
        if self._ao_concluir:
            self._ao_concluir(resultado)

    @Slot(str)
    def erro(self, mensagem: str) -> None:
        if self._ao_falhar:
            self._ao_falhar(mensagem)

    @Slot()
    def terminou(self) -> None:
        self.liberar.emit(self)


class _Trabalhador(QObject):
    concluido = Signal(object)
    falhou = Signal(str)
    finalizado = Signal()

    def __init__(self, funcao: Callable[[], Any]):
        super().__init__()
        self.funcao = funcao

    @Slot()
    def rodar(self) -> None:
        try:
            resultado = self.funcao()
        except Exception as erro:  # noqa: BLE001
            traceback.print_exc()
            self.falhou.emit(f"{erro.__class__.__name__}: {erro}")
        else:
            self.concluido.emit(resultado)
        finally:
            self.finalizado.emit()


class TrabalhoImportacao(QObject):
    """Importação com progresso e cancelamento."""

    progresso = Signal(int, int, str)
    concluido = Signal(object)
    falhou = Signal(str)
    finalizado = Signal()

    def __init__(self, ambiente: Ambiente, caminhos: list[str]):
        super().__init__()
        self.ambiente = ambiente
        self.caminhos = caminhos
        self._cancelar = threading.Event()

    def cancelar(self) -> None:
        self._cancelar.set()

    @Slot()
    def rodar(self) -> None:
        try:
            resultado = self.ambiente.importar(
                self.caminhos,
                progresso=lambda a, b, c: self.progresso.emit(a, b, c),
                cancelado=self._cancelar.is_set,
            )
        except Exception as erro:  # noqa: BLE001
            traceback.print_exc()
            self.falhou.emit(f"{erro.__class__.__name__}: {erro}")
        else:
            self.concluido.emit(resultado)
        finally:
            self.finalizado.emit()


# ----------------------------------------------------------------- formatação

def data_br(texto: str | None) -> str:
    if not texto or len(texto) < 10:
        return texto or ""
    return f"{texto[8:10]}/{texto[5:7]}/{texto[:4]}"


def documento(modelo: str, numero: int | None, serie: int | None) -> str:
    if not numero:
        return "—"
    tipo = "NFC-e" if modelo == "65" else "NF-e"
    return f"{tipo} {numero} · série {serie}"


def cnpj(doc: str | None) -> str:
    return formatar_cnpj(doc) if doc else ""
