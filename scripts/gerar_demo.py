"""Gera uma pasta de demonstração com XMLs fictícios e problemas conhecidos.

Uso:
    python scripts/gerar_demo.py [pasta_destino]

Depois importe a pasta no Conferi AI e, na tela Cliente × Sefaz, use o arquivo
sefaz_padaria_outubro.csv com a Padaria Pão Dourado em outubro de 2026.
"""

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conferi.testing.cenario import gerar_cenario  # noqa: E402


def main() -> None:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("demo_conferi")
    gabarito = gerar_cenario(destino)
    (destino / "gabarito.json").write_text(json.dumps(asdict(gabarito), indent=2, ensure_ascii=False),
                                           encoding="utf-8")
    print(f"Pasta de demonstração criada em: {destino.resolve()}")
    print(f"{gabarito.arquivos_xml} XMLs · {gabarito.notas_unicas} notas únicas · {gabarito.duplicadas} repetidas")
    print("O que o Conferi AI deve encontrar está em gabarito.json")


if __name__ == "__main__":
    main()
