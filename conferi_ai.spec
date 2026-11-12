# -*- mode: python ; coding: utf-8 -*-
# Gera o executável do Conferi AI com PyInstaller:
#   pyinstaller conferi_ai.spec

block_cipher = None

a = Analysis(
    ["run_conferi.py"],
    pathex=[],
    binaries=[],
    datas=[("conferi/assets", "conferi/assets")],
    hiddenimports=["PySide6.QtSvg"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PyQt5", "PyQt6"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ConferiAI",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="ConferiAI",
)
