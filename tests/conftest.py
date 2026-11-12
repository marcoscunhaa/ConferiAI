import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def pasta_dados_isolada(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFERI_DATA_DIR", str(tmp_path / "dados_app"))
    yield
