# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('d_anime_scraper/version.py', 'd_anime_scraper'), ('d_anime_scraper/scraper.py', 'd_anime_scraper')],
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
    name='d_anime_scraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX 圧縮は一部アンチウイルスで誤検知を招きやすいため無効化
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
