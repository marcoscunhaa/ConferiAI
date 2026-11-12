"""Teste de fumaça da interface. Requer PySide6; é pulado se não estiver instalado.

Roda sem abrir janelas (QT_QPA_PLATFORM=offscreen).
"""

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from conferi.core import clientes  # noqa: E402
from conferi.core.servico import Ambiente  # noqa: E402
from conferi.testing.cenario import DISTRIBUIDORA, PADARIA, gerar_cenario  # noqa: E402


@pytest.fixture(scope="module")
def app():
    instancia = QApplication.instance() or QApplication([])
    from conferi.ui import theme

    theme.carregar_fontes()
    instancia.setStyleSheet(theme.folha_de_estilos())
    yield instancia


def test_janela_vazia_e_com_dados(app, tmp_path):
    from conferi.ui.contexto import Contexto
    from conferi.ui.dialogs.nota_detalhe import DialogoNota
    from conferi.ui.janela import JanelaPrincipal

    ambiente = Ambiente.carregar()
    ctx = Contexto(ambiente)
    janela = JanelaPrincipal(ctx)
    janela.show()
    for chave in janela.paginas:
        janela.ir_para(chave, {})
        app.processEvents()

    gabarito = gerar_cenario(tmp_path / "demo")
    ambiente.importar([tmp_path / "demo"])
    clientes.confirmar_sugestoes_automaticamente(ctx.con)
    ambiente.recalcular()
    ctx.avisar_alteracao()
    app.processEvents()

    painel = janela.paginas["painel"]
    assert painel.k_alta.lb_valor.text() == "3"

    janela.ir_para("pendencias", {"cnpj": DISTRIBUIDORA.cnpj, "ano_mes": "2026-10"})
    assert janela.paginas["pendencias"].modelo.rowCount() == 7

    janela.ir_para("notas", {"cnpj": PADARIA.cnpj, "ano_mes": "2026-10"})
    assert janela.paginas["notas"].modelo.rowCount() == 37

    sefaz = janela.paginas["sefaz"]
    sefaz.f_cliente.selecionar(PADARIA.cnpj)
    sefaz.f_periodo.selecionar("2026-10")
    sefaz.arquivo = tmp_path / "demo" / "sefaz_padaria_outubro.csv"
    sefaz._conferir()
    assert sefaz.k_faltando.lb_valor.text() == "1"

    dialogo = DialogoNota(ctx, gabarito.chaves["dist_512"], janela)
    dialogo.show()
    app.processEvents()
    dialogo.close()

    for chave in janela.paginas:
        janela.ir_para(chave, {})
        app.processEvents()
    janela.close()
