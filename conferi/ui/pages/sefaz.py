"""Conferência cliente × Sefaz."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QMessageBox, QTabWidget

from conferi.core import consultas, sefaz
from conferi.core.exporters.excel import exportar_conferencia
from conferi.core.money import fmt_brl

from .. import theme
from ..contexto import Contexto, data_br
from ..tabela import Coluna, criar_tabela
from ..widgets import Banner, Card, Combo, EstadoVazio, KpiCard, Pagina, Rotulado, botao, rotulo

SIT = {
    "autorizada": ("Autorizada", theme.GREEN, theme.GREEN_SOFT),
    "cancelada": ("Cancelada", theme.RED, theme.RED_SOFT),
    "denegada": ("Denegada", theme.RED, theme.RED_SOFT),
    "não consta": ("Não consta", theme.AMBER, theme.AMBER_SOFT),
    "ativa": ("Ativa", theme.GREEN, theme.GREEN_SOFT),
    "não recebida": ("Não recebida", theme.AMBER, theme.AMBER_SOFT),
    "desconhecida": ("Sem situação", theme.MUTED, theme.GREY_SOFT),
}


class PaginaSefaz(Pagina):
    def __init__(self, ctx: Contexto):
        super().__init__("Conferência com a Sefaz", "Cliente × Sefaz",
                         "Compare as notas que o cliente enviou com a relação de notas registradas na Sefaz.",
                         rolagem=True)
        self.ctx = ctx
        self.arquivo: Path | None = None
        self.resultado: sefaz.ResultadoConferencia | None = None

        self.vazio = EstadoVazio("sefaz", "Importe as notas antes de conferir",
                                 "A conferência compara as notas importadas de um cliente com o arquivo baixado do "
                                 "portal da Sefaz.", "Importar XMLs", lambda: ctx.navegar.emit("importar", {}))
        self.layout_pagina.addWidget(self.vazio)

        self.card_passos = Card("Nova conferência")
        passos = QHBoxLayout()
        passos.setSpacing(14)
        self.f_cliente = Combo(260)
        self.f_periodo = Combo(180)
        self.lb_arquivo = rotulo("Nenhum arquivo selecionado", "Small")
        bt_arquivo = botao("Selecionar arquivo da Sefaz", "Ghost", "arquivo", self._escolher)
        passos.addWidget(Rotulado("1 · Cliente", self.f_cliente))
        passos.addWidget(Rotulado("2 · Período", self.f_periodo))
        passos.addWidget(Rotulado("3 · Arquivo do portal", bt_arquivo))
        passos.addStretch(1)
        self.bt_conferir = botao("Conferir", "Gold", "sefaz", self._conferir)
        passos.addWidget(self.bt_conferir)
        self.card_passos.corpo.addLayout(passos)
        self.card_passos.corpo.addWidget(self.lb_arquivo)
        self.card_passos.corpo.addWidget(Banner(
            "Aceita CSV, TXT ou XLSX exportados do portal. O Conferi AI procura as chaves de acesso em cada linha e "
            "identifica a situação por palavras como <i>autorizada</i>, <i>cancelada</i> ou <i>denegada</i>. São "
            "consideradas as notas emitidas pelo cliente no mês escolhido.", "BannerInfo", "info"))
        self.layout_pagina.addWidget(self.card_passos)

        self.avisos = Banner("", "Banner", "alerta")
        self.avisos.hide()
        self.layout_pagina.addWidget(self.avisos)

        self.card_res = Card("Resultado", acao=botao("Exportar Excel", "Ghost", "excel", self._exportar))
        grade = QGridLayout()
        grade.setSpacing(12)
        self.k_faltando = KpiCard("Faltando no escritório", theme.RED)
        self.k_fora = KpiCard("Fora da Sefaz", theme.AMBER)
        self.k_canc_sefaz = KpiCard("Canceladas na Sefaz", theme.RED)
        self.k_canc_esc = KpiCard("Canceladas só no escritório", theme.BLUE)
        self.k_ok = KpiCard("Conferem", theme.GREEN)
        for i, k in enumerate((self.k_faltando, self.k_fora, self.k_canc_sefaz, self.k_canc_esc, self.k_ok)):
            grade.addWidget(k, 0, i)
        self.card_res.corpo.addLayout(grade)
        self.lb_res = rotulo("", "Muted", quebra=True)
        self.card_res.corpo.addWidget(self.lb_res)

        self.abas = QTabWidget()
        self.tabelas = {}
        for chave in ("faltando_no_escritorio", "fora_da_sefaz", "cancelada_na_sefaz", "cancelada_no_escritorio",
                      "conferem"):
            tabela, modelo, _ = criar_tabela([
                Coluna("modelo", "Modelo", formato=lambda v: "NFC-e" if v == "65" else "NF-e", largura=80),
                Coluna("serie", "Série", alinhamento="direita", largura=70),
                Coluna("numero", "Número", alinhamento="direita", largura=100),
                Coluna("data", "Data", formato=lambda v: data_br(v) or "—", largura=100),
                Coluna("valor", "Valor", formato=lambda v: fmt_brl(v) if v is not None else "—",
                       alinhamento="direita", largura=130),
                Coluna("situacao_sefaz", "Na Sefaz", largura=130, pilula=lambda v: SIT.get(v)),
                Coluna("situacao_escritorio", "No escritório", largura=140, pilula=lambda v: SIT.get(v)),
                Coluna("chave", "Chave de acesso", esticar=True),
            ], 40)
            tabela.setMinimumHeight(300)
            self.tabelas[chave] = (tabela, modelo)
            self.abas.addTab(tabela, "")
        self.card_res.corpo.addWidget(self.abas)
        self.card_res.hide()
        self.layout_pagina.addWidget(self.card_res)
        self.layout_pagina.addStretch(1)

        ctx.dados_alterados.connect(self.atualizar)
        self.atualizar()

    def atualizar(self) -> None:
        con = self.ctx.con
        periodos = consultas.periodos(con)
        self.vazio.setVisible(not periodos)
        self.card_passos.setVisible(bool(periodos))
        self.f_cliente.preencher([(r["nome"], r["cnpj"]) for r in consultas.lista_clientes(con)])
        self.f_periodo.preencher([(consultas.rotulo_periodo(p), p) for p in periodos])

    def _escolher(self) -> None:
        pasta = self.ctx.ambiente.config.ultima_pasta_importacao or str(Path.home())
        arquivo, _ = QFileDialog.getOpenFileName(self, "Arquivo da Sefaz", pasta,
                                                 "Relação de notas (*.csv *.txt *.xlsx);;Todos os arquivos (*)")
        if arquivo:
            self.arquivo = Path(arquivo)
            self.lb_arquivo.setText(f"Arquivo: {self.arquivo.name}")

    def _conferir(self) -> None:
        if not self.f_cliente.currentData():
            QMessageBox.information(self, "Selecione o cliente", "Confirme os clientes antes de conferir.")
            return
        if not self.arquivo:
            QMessageBox.information(self, "Selecione o arquivo", "Escolha o arquivo baixado do portal da Sefaz.")
            return
        try:
            leitura = sefaz.ler_arquivo_sefaz(self.arquivo)
        except Exception as erro:  # noqa: BLE001
            QMessageBox.critical(self, "Não foi possível ler o arquivo", str(erro))
            return
        cnpj_cli, am = self.f_cliente.currentData(), self.f_periodo.currentData()
        r = sefaz.conferir(self.ctx.con, cnpj_cli, am, leitura)
        self.resultado = r

        avisos = list(leitura.avisos)
        if leitura.chaves_invalidas:
            avisos.append(f"{leitura.chaves_invalidas} chave(s) com dígito verificador inválido foram ignoradas.")
        if r.registros_outros_periodos:
            avisos.append(f"{r.registros_outros_periodos} nota(s) do arquivo são de outro CNPJ ou outro mês e não "
                          "entraram na conferência.")
        self.avisos.definir("<br>".join(avisos))
        self.avisos.setVisible(bool(avisos))

        grupos = (("faltando_no_escritorio", "Faltando no escritório", self.k_faltando,
                   "emitidas, mas não enviadas pelo cliente"),
                  ("fora_da_sefaz", "Fora da Sefaz", self.k_fora, "recebidas, mas não constam no arquivo"),
                  ("cancelada_na_sefaz", "Canceladas na Sefaz", self.k_canc_sefaz,
                   "o escritório não recebeu o cancelamento"),
                  ("cancelada_no_escritorio", "Canceladas só no escritório", self.k_canc_esc,
                   "a Sefaz informa como autorizadas"),
                  ("conferem", "Conferem", self.k_ok, "sem divergência"))
        for i, (chave, titulo, kpi, sub) in enumerate(grupos):
            lista = getattr(r, chave)
            kpi.definir(str(len(lista)), sub)
            self.tabelas[chave][1].definir_linhas(lista)
            self.abas.setTabText(i, f"{titulo} ({len(lista)})")
        primeira = next((i for i, (c, *_r) in enumerate(grupos) if getattr(r, c)), 4)
        self.abas.setCurrentIndex(primeira)
        nome = self.f_cliente.currentText()
        if r.total_divergencias:
            self.lb_res.setText(f"{nome} · {consultas.rotulo_periodo(am)}: {r.total_divergencias} divergência(s) "
                                "para resolver antes de enviar.")
        else:
            self.lb_res.setText(f"{nome} · {consultas.rotulo_periodo(am)}: tudo confere com a Sefaz.")
        self.card_res.show()

    def _exportar(self) -> None:
        if not self.resultado:
            return
        pasta = self.ctx.ambiente.config.ultima_pasta_exportacao or str(Path.home())
        nome = self.f_cliente.currentText()
        destino, _ = QFileDialog.getSaveFileName(
            self, "Salvar conferência", str(Path(pasta) / f"Conferencia Sefaz {nome} {self.resultado.ano_mes}.xlsx"),
            "Excel (*.xlsx)")
        if not destino:
            return
        try:
            exportar_conferencia(self.resultado, destino, nome)
        except Exception as erro:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao exportar", str(erro))
            return
        QMessageBox.information(self, "Conferência exportada", f"Salva em:\n{destino}")
