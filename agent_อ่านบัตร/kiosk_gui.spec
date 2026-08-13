# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for NHSO Kiosk Agent GUI
# Build: pyinstaller kiosk_gui.spec

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.ini', '.'),
    ],
    hiddenimports=['requests', 'pystray', 'pystray._win32', 'PIL', 'PIL.Image', 'PIL.ImageDraw'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy', 'scipy', 'matplotlib', 'pandas',
        'cryptography', 'cffi', 'bcrypt', 'nacl',
        'psutil', 'gi', 'pytest', 'setuptools',
        'pip', 'distutils', 'unittest', 'pydoc',
        'lib2to3', 'ensurepip', 'venv',
        'tkinter.test', 'test',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NHSO_Kiosk_Agent_GUI',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NHSO_Kiosk_Agent_GUI',
)
