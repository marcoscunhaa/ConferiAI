"""Configurações do aplicativo, salvas em JSON na pasta de dados do usuário."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from platformdirs import user_data_dir

from conferi import APP_AUTHOR, APP_NAME


def pasta_dados() -> Path:
    """Pasta local do aplicativo. Pode ser sobrescrita com CONFERI_DATA_DIR (testes)."""
    base = os.environ.get("CONFERI_DATA_DIR")
    pasta = Path(base) if base else Path(user_data_dir(APP_NAME, APP_AUTHOR))
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def caminho_banco() -> Path:
    return pasta_dados() / "conferi.db"


def caminho_config() -> Path:
    return pasta_dados() / "config.json"


@dataclass
class ConfigRegras:
    tolerancia_total_centavos: int = 5          # diferença aceita entre total e composição
    ibscbs_ativo: bool = True
    ibscbs_inicio: str = "2026-01-01"           # notas emitidas a partir desta data
    ibscbs_crts: list[str] = field(default_factory=lambda: ["3"])  # 3 = regime normal
    tabela_ncm: str = ""                        # caminho opcional da tabela NCM vigente
    lacuna_maxima_detalhada: int = 200          # lacunas maiores viram um único alerta


@dataclass
class ConfigBackup:
    pasta: str = ""
    manter: int = 10
    automatico: bool = True
    ultimo_backup: str = ""


@dataclass
class AppConfig:
    regras: ConfigRegras = field(default_factory=ConfigRegras)
    backup: ConfigBackup = field(default_factory=ConfigBackup)
    ultima_pasta_importacao: str = ""
    ultima_pasta_exportacao: str = ""
    primeira_execucao: bool = True

    # ------------------------------------------------------------- persistência
    @classmethod
    def carregar(cls, caminho: Path | None = None) -> "AppConfig":
        caminho = caminho or caminho_config()
        if not caminho.exists():
            return cls()
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        cfg = cls()
        cfg.regras = _preencher(ConfigRegras, dados.get("regras", {}))
        cfg.backup = _preencher(ConfigBackup, dados.get("backup", {}))
        for nome in ("ultima_pasta_importacao", "ultima_pasta_exportacao", "primeira_execucao"):
            if nome in dados:
                setattr(cfg, nome, dados[nome])
        return cfg

    def salvar(self, caminho: Path | None = None) -> None:
        caminho = caminho or caminho_config()
        temporario = caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporario, caminho)  # escrita atômica


def _preencher(tipo, dados: dict):
    obj = tipo()
    validos = {f.name for f in fields(tipo)}
    for chave, valor in dados.items():
        if chave in validos:
            setattr(obj, chave, valor)
    return obj
