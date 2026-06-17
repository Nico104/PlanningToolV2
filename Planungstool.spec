# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Nico\\Documents\\Bachelorarbeit\\plannerV2\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Nico\\Documents\\Bachelorarbeit\\plannerV2\\default_tables', 'default_tables'), ('C:\\Users\\Nico\\Documents\\Bachelorarbeit\\plannerV2\\src\\settings.json', 'src'), ('C:\\Users\\Nico\\Documents\\Bachelorarbeit\\plannerV2\\src\\studiensemester.json', 'src'), ('C:\\Users\\Nico\\Documents\\Bachelorarbeit\\plannerV2\\src\\konflikte.json', 'src'), ('C:\\Users\\Nico\\Documents\\Bachelorarbeit\\plannerV2\\src\\ui\\styles', 'src\\ui\\styles'), ('C:\\Users\\Nico\\Documents\\Bachelorarbeit\\plannerV2\\src\\ui\\assets', 'src\\ui\\assets')],
    hiddenimports=[],
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
    name='Planungstool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\Nico\\Documents\\Bachelorarbeit\\plannerV2\\src\\ui\\assets\\icons\\app_icon.ico'],
)
