# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('goae_data.json', '.'),
        ('config.json', '.'),
    ],
    hiddenimports=[
        'ocr', 'parser', 'goae_db', 'auto_entry', 'ui',
        'cv2', 'numpy', 'pyautogui', 'pytesseract',
        'keyboard', 'PIL', 'pynput', 'pynput.keyboard',
        'pynput.keyboard._win32', 'pynput.mouse', 'pynput.mouse._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GOAe-Assistent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
)
