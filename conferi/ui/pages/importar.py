"""Importação de XMLs: arrastar e soltar, progresso e resultado."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
)

from conferi.core import clientes, consultas
from conferi.core.importer import ResultadoImportacao

from .. import theme
from ..contexto import Contexto, TrabalhoImportacao, data_br
from ..dialogs.confirmar_clientes import DialogoConfirmarClientes
from ..icons import pixmap
from ..tabela import Coluna, criar_tabela
from ..widgets import Banner, Card, KpiCard, Pagina, botao, rotulo


class AreaSoltar(QFrame):
    soltou = Signal(list)

    def __init__(self, ao_pasta, ao_arquivos):
        super().__init__()
        self.setObjectName("Dropzone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(250)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)
        circulo = QLabel()
        circulo.setFixedSize(68, 68)
        circulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circulo.setPixmap(pixmap("nuvem", theme.GOLD, 30))
        circulo.setStyleSheet(f"background: {theme.GOLD_SOFT}; border-radius: 34px;")
        lay.addWidget(circulo, alignment=Qt.AlignmentFlag.AlignHCenter)
        titulo = rotulo("Arraste aqui as pastas, XMLs ou arquivos .zip", "EmptyTitle")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(titulo)
        sub = rotulo("NF-e, NFC-e, eventos de cancelamento e inutilizações. Subpastas são lidas automaticamente.",
                     "Muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub)
        botoes = QHBoxLayout()
        botoes.setSpacing(10)
        botoes.addStretch(1)
        botoes.addWidget(botao("Selecionar pasta", "Primary", "pasta", ao_pasta))
        botoes.addWidget(botao("Selecionar arquivos", "Ghost", "arquivo", ao_arquivos))
        botoes.addStretch(1)
        lay.addSpacing(6)
        lay.addLayout(botoes)

    def _ativo(self, valor: bool) -> None:
        self.setProperty("ativo", "true" if valor else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, ev):  # noqa: N802
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()
            self._ativo(True)

    def dragLeaveEvent(self, ev):  # noqa: N802
        self._ativo(False)

    def dropEvent(self, ev):  # noqa: N802
        self._ativo(False)
        caminhos = [u.toLocalFile() for u in ev.mimeData().urls() if u.isLocalFile()]
        if caminhos:
            self.soltou.emit(caminhos)


class PaginaImportar(Pagina):
    def __init__(self, ctx: Contexto):
        super().__init__("Entrada de documentos", "Importar XMLs", rolagem=True)
        self.ctx = ctx
        self.thread: QThread | None = None
        self.trabalho: TrabalhoImportacao | None = None

        self.area = AreaSoltar(self._escolher_pasta, self._escolher_arquivos)
        self.area.soltou.connect(self.iniciar)
        self.layout_pagina.addWidget(self.area)

        privacidade = Banner("<b>Seus dados ficam aqui.</b> Os arquivos são lidos neste computador e nenhum XML é "
                             "enviado para a internet. Antes de cada importação, o Conferi AI faz um backup da base.",
                             "BannerInfo", "escudo")
        self.layout_pagina.addWidget(privacidade)

        # Progresso
        self.card_prog = Card("Importando…")
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.lb_prog = rotulo("", "Small")
        self.lb_prog.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        linha = QHBoxLayout()
        linha.addWidget(self.lb_prog, 1)
        self.bt_cancelar = botao("Cancelar", "Ghost", "x", self._cancelar)
        linha.addWidget(self.bt_cancelar)
        self.card_prog.corpo.addWidget(self.barra)
        self.card_prog.corpo.addLayout(linha)
        self.card_prog.hide()
        self.layout_pagina.addWidget(self.card_prog)

        # Resultado
        self.card_res = Card("Resultado da importação")
        grade = QGridLayout()
        grade.setSpacing(12)
        self.k_novas = KpiCard("Notas novas", theme.GREEN)
        self.k_rep = KpiCard("Repetidas ignoradas", theme.NAVY)
        self.k_ev = KpiCard("Eventos e inutilizações", theme.BLUE)
        self.k_prob = KpiCard("Arquivos com problema", theme.RED)
        for i, k in enumerate((self.k_novas, self.k_rep, self.k_ev, self.k_prob)):
            grade.addWidget(k, 0, i)
        self.card_res.corpo.addLayout(grade)
        self.lb_res = rotulo("", "Muted", quebra=True)
        self.card_res.corpo.addWidget(self.lb_res)
        self.tab_rej, self.mod_rej, _ = criar_tabela([
            Coluna("tipo", "Tipo", largura=120, pilula=lambda v: ("Ignorado", theme.MUTED, theme.GREY_SOFT)
                   if v == "ignorado" else ("Inválido", theme.RED, theme.RED_SOFT)),
            Coluna(lambda r: Path(r["arquivo"].split("::")[-1]).name, "Arquivo", largura=320,
                   dica=lambda r: r["arquivo"]),
            Coluna("motivo", "Motivo", esticar=True),
        ], 38)
        self.tab_rej.setMinimumHeight(160)
        self.card_res.corpo.addWidget(self.tab_rej)
        acoes = QHBoxLayout()
        acoes.addStretch(1)
        acoes.addWidget(botao("Ver notas", "Ghost", "notas", lambda: ctx.navegar.emit("notas", {})))
        acoes.addWidget(botao("Ver pendências", "Primary", "pendencias", lambda: ctx.navegar.emit("pendencias", {})))
        self.card_res.corpo.addLayout(acoes)
        self.card_res.hide()
        self.layout_pagina.addWidget(self.card_res)

        # Histórico
        self.card_hist = Card("Histórico de importações")
        self.tab_hist, self.mod_hist, _ = criar_tabela([
            Coluna(lambda r: f"{data_br(r['iniciado_em'][:10])} {r['iniciado_em'][11:16]}", "Quando", largura=150),
            Coluna("origem", "Origem", esticar=True),
            Coluna("total_arquivos", "Arquivos", alinhamento="direita", largura=90),
            Coluna("notas_novas", "Novas", alinhamento="direita", largura=80),
            Coluna("duplicadas", "Repetidas", alinhamento="direita", largura=90),
            Coluna(lambda r: r["eventos"] + r["inutilizacoes"], "Eventos", alinhamento="direita", largura=80),
            Coluna("invalidos", "Problemas", alinhamento="centro", largura=100,
                   pilula=lambda v: (str(v), theme.RED, theme.RED_SOFT) if v else ("0", theme.GREEN, theme.GREEN_SOFT)),
        ], 40)
        self.tab_hist.setMinimumHeight(200)
        self.card_hist.corpo.addWidget(self.tab_hist)
        self.layout_pagina.addWidget(self.card_hist)
        self.layout_pagina.addStretch(1)

        ctx.dados_alterados.connect(self.atualizar)
        self.atualizar()

    # ------------------------------------------------------------------
    def aplicar_filtros(self, filtros: dict) -> None:
        if filtros.get("caminhos"):
            self.iniciar(filtros["caminhos"])

    def atualizar(self) -> None:
        historico = consultas.ultimas_importacoes(self.ctx.con, 20)
        self.mod_hist.definir_linhas(historico)
        self.card_hist.setVisible(bool(historico))

    def _escolher_pasta(self) -> None:
        inicial = self.ctx.ambiente.config.ultima_pasta_importacao or str(Path.home())
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar pasta com XMLs", inicial)
        if pasta:
            self.iniciar([pasta])

    def _escolher_arquivos(self) -> None:
        inicial = self.ctx.ambiente.config.ultima_pasta_importacao or str(Path.home())
        arquivos, _ = QFileDialog.getOpenFileNames(self, "Selecionar XMLs ou .zip", inicial,
                                                   "Documentos fiscais (*.xml *.zip);;Todos os arquivos (*)")
        if arquivos:
            self.iniciar(arquivos)

    def iniciar(self, caminhos: list[str]) -> None:
        if self.thread is not None:
            return
        cfg = self.ctx.ambiente.config
        primeiro = Path(caminhos[0])
        cfg.ultima_pasta_importacao = str(primeiro if primeiro.is_dir() else primeiro.parent)
        cfg.salvar()

        self.area.setEnabled(False)
        self.card_res.hide()
        self.card_prog.show()
        self.barra.setRange(0, 0)
        self.lb_prog.setText("Preparando: fazendo backup e contando arquivos…")
        self.bt_cancelar.setEnabled(True)

        self.thread = QThread()
        self.trabalho = TrabalhoImportacao(self.ctx.ambiente, caminhos)
        self.trabalho.moveToThread(self.thread)
        self.thread.started.connect(self.trabalho.rodar)
        self.trabalho.progresso.connect(self._progresso)
        self.trabalho.concluido.connect(self._concluido)
        self.trabalho.falhou.connect(self._falhou)
        self.trabalho.finalizado.connect(self.thread.quit)
        self.thread.finished.connect(self._limpar_thread)
        self.thread.start()

    def _cancelar(self) -> None:
        if self.trabalho:
            self.trabalho.cancelar()
            self.bt_cancelar.setEnabled(False)
            self.lb_prog.setText("Cancelando… as notas já lidas serão mantidas.")

    def _progresso(self, atual: int, total: int, arquivo: str) -> None:
        if total:
            self.barra.setRange(0, total)
            self.barra.setValue(atual)
        nome = Path(arquivo.split("::")[-1]).name if arquivo else ""
        texto = f"{atual:,} de {total:,} arquivos".replace(",", ".")
        if nome:
            texto += f"  ·  {nome}"
        if atual >= total:
            texto = "Conferindo as notas e calculando as pendências…"
            self.barra.setRange(0, 0)
        self.lb_prog.setText(texto)

    def _limpar_thread(self) -> None:
        if self.thread:
            self.thread.deleteLater()
        if self.trabalho:
            self.trabalho.deleteLater()
        self.thread = None
        self.trabalho = None
        self.area.setEnabled(True)
        self.card_prog.hide()

    def _falhou(self, mensagem: str) -> None:
        QMessageBox.critical(self, "Não foi possível concluir a importação",
                             f"Ocorreu um erro durante a importação:\n\n{mensagem}\n\n"
                             "As notas já gravadas foram mantidas e o backup anterior continua disponível.")

    def _concluido(self, r: ResultadoImportacao) -> None:
        if r.total_arquivos == 0:
            QMessageBox.information(self, "Nenhum XML encontrado",
                                    "Não encontramos arquivos .xml ou .zip no que foi selecionado.")
            return
        self.card_res.show()
        self.k_novas.definir(str(r.notas_novas), f"{r.notas_atualizadas} atualizadas com protocolo"
                             if r.notas_atualizadas else "notas gravadas na base")
        self.k_rep.definir(str(r.duplicadas), "identificadas pela chave de acesso")
        self.k_ev.definir(str(r.eventos + r.inutilizacoes),
                          f"{r.eventos} eventos · {r.inutilizacoes} inutilizações")
        self.k_prob.definir(str(len(r.invalidos) + len(r.ignorados)),
                            f"{len(r.invalidos)} inválidos · {len(r.ignorados)} ignorados")
        resumo = f"{r.total_arquivos:,} arquivos lidos em {r.segundos:.1f} s.".replace(",", ".")
        if r.interrompida:
            resumo = "Importação cancelada. " + resumo
        if r.empresas_novas:
            resumo += f" {r.empresas_novas} empresa(s) nova(s) identificada(s) nas notas."
        self.lb_res.setText(resumo)
        rejeitados = consultas.rejeitados(self.ctx.con, r.importacao_id)
        self.mod_rej.definir_linhas(rejeitados)
        self.tab_rej.setVisible(bool(rejeitados))

        if clientes.existem_pendentes_de_confirmacao(self.ctx.con):
            dialogo = DialogoConfirmarClientes(self.ctx, self)
            dialogo.exec()
        self.ctx.avisar_alteracao()
