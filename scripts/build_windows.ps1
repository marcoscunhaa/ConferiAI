# Gera o executável e o instalador do Conferi AI no Windows.
# Requisitos: Python 3.11+, Inno Setup 6 (iscc no PATH).
# Uso (PowerShell, na raiz do projeto):  .\scripts\build_windows.ps1

$ErrorActionPreference = "Stop"

python -m venv .venv-build
.\.venv-build\Scripts\python -m pip install --upgrade pip
.\.venv-build\Scripts\pip install -r requirements-dev.txt

.\.venv-build\Scripts\python -m pytest -q
.\.venv-build\Scripts\pyinstaller --noconfirm conferi_ai.spec

if (Get-Command iscc -ErrorAction SilentlyContinue) {
    iscc installer\conferi_ai.iss
    Write-Host "Instalador gerado em dist\instalador"
} else {
    Write-Host "Inno Setup não encontrado. O executável está em dist\ConferiAI\ConferiAI.exe"
}
