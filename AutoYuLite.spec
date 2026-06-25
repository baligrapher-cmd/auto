# -*- mode: python ; coding: utf-8 -*-


import os
os.environ['MACOSX_DEPLOYMENT_TARGET'] = '11.0'

a = Analysis(
    ['main_lite.py'],
    pathex=[],
    binaries=[],
    datas=[('PANDUAN_USER.txt', '.'), ('icon.ico', '.')],
    hiddenimports=['encodings', 'encodings.utf_8', 'encodings.latin_1'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Determine icon path cross-platform
icon_path = os.path.join('assets', 'icon.ico')
if not os.path.exists(icon_path):
    icon_path = 'icon.ico'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoYuLite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[icon_path],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AutoYuLite',
)

# Use icon.icns if generated (macOS), otherwise fallback to None
icns_path = 'icon.icns'
if not os.path.exists(icns_path):
    icns_path = None

app = BUNDLE(
    coll,
    name='AutoYuLite.app',
    icon=icns_path,
    bundle_identifier='pramana.autoyu.lite',
)
