"""Janela principal: barra lateral de navegação e páginas."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from conferi import APP_NAME, __version__
from conferi.core import consultas

from . import theme
from .contexto import Contexto
from .icons import pixmap
from .pages.clientes import PaginaClientes
from .pages.configuracoes import PaginaConfiguracoes
from .pages.importar import PaginaImportar
from .pages.notas import PaginaNotas
from .pages.painel import PaginaPainel
from .pages.pendencias import PaginaPendencias
from .pages.relatorios import PaginaRelatorios
from .pages.sefaz import PaginaSefaz
from .widgets import Monograma, rotulo


class ItemNavegacao(QPushButton):
    def __init__(self, icone_nome: str, texto: str):
        super().__init__()
        self.setObjectName("NavItem")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self.icone_nome = icone_nome
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 10, 0)
        lay.setSpacing(10)
        self.marcador = QFrame()
        self.marcador.setFixedSize(3, 22)
        lay.addWidget(self.marcador)
        self.ic = QLabel()
        self.ic.setFixedSize(QSize(18, 18))
        lay.addWidget(self.ic)
        self.lb = QLabel(texto)
        lay.addWidget(self.lb, 1)
        self.badge = QLabel()
        self.badge.hide()
        lay.addWidget(self.badge)
        for w in (self.marcador, self.ic, self.lb, self.badge):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.toggled.connect(self._estilo)
        self._estilo(False)

    def _estilo(self, ativo: bool) -> None:
        cor = "#FFFFFF" if ativo else "#AEB8C8"
        self.ic.setPixmap(pixmap(self.icone_nome, cor, 18))
        self.lb.setStyleSheet(f"font-family: '{theme.SANS}'; font-size: 13px; font-weight: 500; color: {cor};")
        self.marcador.setStyleSheet(f"background: {theme.GOLD if ativo else 'transparent'}; border-radius: 1px;")

    def definir_badge(self, valor: int) -> None:
        if valor:
            self.badge.setText(str(valor) if valor < 1000 else "999+")
            self.badge.setStyleSheet(f"background: {theme.RED}; color: white; font-family: '{theme.SANS}';"
                                     "font-size: 10px; font-weight: 600; border-radius: 9px; padding: 1px 7px;")
            self.badge.show()
        else:
            self.badge.hide()


class JanelaPrincipal(QMainWindow):
    PAGINAS = [
        ("painel", "painel", "Painel"),
        ("importar", "importar", "Importar XMLs"),
        ("clientes", "clientes", "Clientes"),
        ("notas", "notas", "Notas fiscais"),
        ("pendencias", "pendencias", "Pendências"),
        ("sefaz", "sefaz", "Cliente × Sefaz"),
        ("relatorios", "relatorios", "Relatórios"),
        ("configuracoes", "config", "Configurações"),
    ]

    def __init__(self, ctx: Contexto):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)

        central = QWidget()
        central.setObjectName("Content")
        raiz = QHBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._barra_lateral())

        self.pilha = QStackedWidget()
        self.pilha.setObjectName("Content")
        self.paginas = {
            "painel": PaginaPainel(ctx),
            "importar": PaginaImportar(ctx),
            "clientes": PaginaClientes(ctx),
            "notas": PaginaNotas(ctx),
            "pendencias": PaginaPendencias(ctx),
            "sefaz": PaginaSefaz(ctx),
            "relatorios": PaginaRelatorios(ctx),
            "configuracoes": PaginaConfiguracoes(ctx),
        }
        for pagina in self.paginas.values():
            self.pilha.addWidget(pagina)
        raiz.addWidget(self.pilha, 1)
        self.setCentralWidget(central)

        ctx.navegar.connect(self.ir_para)
        ctx.dados_alterados.connect(self._atualizar_lateral)
        self.ir_para("painel", {})
        self._atualizar_lateral()

    def _barra_lateral(self) -> QWidget:
        lateral = QFrame()
        lateral.setObjectName("Sidebar")
        lateral.setFixedWidth(248)
        lay = QVBoxLayout(lateral)
        lay.setContentsMargins(16, 24, 16, 20)
        lay.setSpacing(4)

        marca = QHBoxLayout()
        marca.setContentsMargins(6, 0, 0, 0)
        marca.setSpacing(10)
        marca.addWidget(Monograma(36))
        nome = rotulo("Conferi", "SidebarBrand")
        marca.addWidget(nome)
        ai = rotulo("AI", "SidebarBrandAI")
        ai.setAlignment(Qt.AlignmentFlag.AlignBottom)
        marca.addWidget(ai)
        marca.addStretch(1)
        lay.addLayout(marca)
        lay.addSpacing(26)

        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.itens: dict[str, ItemNavegacao] = {}
        for chave, icone_nome, texto in self.PAGINAS:
            if chave == "relatorios":
                lay.addSpacing(10)
            item = ItemNavegacao(icone_nome, texto)
            item.clicked.connect(lambda _=False, c=chave: self.ir_para(c, {}))
            self.grupo.addButton(item)
            self.itens[chave] = item
            lay.addWidget(item)
        lay.addStretch(1)

        divisor = QFrame()
        divisor.setObjectName("SidebarDivider")
        lay.addWidget(divisor)
        lay.addSpacing(10)
        self.lb_backup_titulo = rotulo("Último backup", "SidebarFootTitle")
        self.lb_backup = rotulo("", "SidebarFoot")
        self.lb_integridade = rotulo("● Base local íntegra", "SidebarFoot")
        self.lb_integridade.setStyleSheet("color: #7FC4A2;")
        self.lb_import_titulo = rotulo("Última importação", "SidebarFootTitle")
        self.lb_import = rotulo("", "SidebarFoot")
        for w in (self.lb_backup_titulo, self.lb_backup, self.lb_integridade):
            lay.addWidget(w)
        lay.addSpacing(8)
        lay.addWidget(self.lb_import_titulo)
        lay.addWidget(self.lb_import)
        lay.addSpacing(8)
        lay.addWidget(rotulo(f"Versão {__version__} · processamento local", "SidebarFoot"))
        return lateral

    def ir_para(self, chave: str, filtros: dict) -> None:
        pagina = self.paginas.get(chave)
        if pagina is None:
            return
        self.itens[chave].setChecked(True)
        self.pilha.setCurrentWidget(pagina)
        if filtros and hasattr(pagina, "aplicar_filtros"):
            pagina.aplicar_filtros(filtros)

    def _atualizar_lateral(self) -> None:
        k = consultas.kpis(self.ctx.con, None)
        self.itens["pendencias"].definir_badge(k.pendencias_alta)
        self.lb_backup.setText(f"{self.ctx.ambiente.ultimo_backup_rotulo()}")
        ultimas = consultas.ultimas_importacoes(self.ctx.con, 1)
        if ultimas:
            u = ultimas[0]
            quando = u["iniciado_em"]
            qtd = f"{u['total_arquivos']:,}".replace(",", ".")
            self.lb_import.setText(f"{qtd} arquivos · {quando[8:10]}/{quando[5:7]}, {quando[11:16]}")
        else:
            self.lb_import.setText("Nenhuma ainda")

    def closeEvent(self, ev):  # noqa: N802
        amb = self.ctx.ambiente
        if self.ctx.tarefas_ativas() or self.paginas["importar"].thread is not None:
            ev.ignore()
            self.statusBar().showMessage("Aguarde a tarefa em andamento terminar antes de fechar.", 5000)
            return
        if amb.config.backup.automatico:
            try:
                if self.ctx.con.execute("SELECT 1 FROM notas LIMIT 1").fetchone():
                    self.ctx.con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    amb.fazer_backup()
            except Exception:  # noqa: BLE001 — fechar nunca deve falhar por causa do backup
                pass
        self.ctx.fechar()
        super().closeEvent(ev)
