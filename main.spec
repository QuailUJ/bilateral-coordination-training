# -*- mode: python ; coding: utf-8 -*-
"""
main.spec - PyInstaller 打包設定

跟 BilateralCoordinationTraining 舊版 spec 比，修正兩個已知的坑：
    1. mediapipe 的 datas 路徑改成用 mediapipe.__file__ 動態算出來，不要寫死
       在某台開發機器的絕對路徑（舊版寫死 C:\\Users\\fangt\\...\\Python310\\...，
       換一台電腦/換虛擬環境打包就會直接找不到）。
    2. 明確把 assets/ 跟 model/ 加進 datas——這兩個資料夾裡的字型/模型檔案是
       common/paths.py::resource_path() 在 frozen 模式下唯一會去找的地方
       （sys._MEIPASS），舊版 spec 忘記加這段，打包出來的 exe 會找不到字型/模型。

不打包 data/（使用者存檔）：這個資料夾應該由執行時的 resource_path() 在使用者
電腦上自然建立/寫入，不該把開發機器上的測試帳號存檔一起塞進安裝檔。

用法：
    pyinstaller main.spec
"""

import os

import mediapipe

MEDIAPIPE_DIR = os.path.dirname(mediapipe.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (MEDIAPIPE_DIR, 'mediapipe'),
        ('assets', 'assets'),
        ('model', 'model'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'tensorflow', 'tensorboard', 'keras'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)
