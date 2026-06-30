# -*- mode: python ; coding: utf-8 -*-


import os
import sys
from PyInstaller.utils.hooks import collect_data_files
os.environ['MACOSX_DEPLOYMENT_TARGET'] = '11.0'

# Determine target architecture
target_arch = os.environ.get('TARGET_ARCH', None)
if sys.platform == 'darwin' and not target_arch:
    # Try to detect from sys.platform
    import platform
    machine = platform.machine()
    if machine == 'x86_64':
        target_arch = 'x86_64'
    elif machine == 'arm64':
        target_arch = 'arm64'

# Collect Playwright's data files (driver, etc.)
playwright_datas = collect_data_files('playwright')

# Collect browsers folder if available (for CI builds, only Windows/Linux, macOS handled manually in workflow)
datas_list = [('PANDUAN_USER.txt', '.'), ('icon.ico', '.')] + playwright_datas
if sys.platform != 'darwin':
    if os.path.exists('browsers'):
        print(f"[SPEC] Adding browsers folder to bundle...")
        datas_list.append(('browsers', 'browsers'))
    if os.path.exists('pw-browsers'):
        print(f"[SPEC] Adding pw-browsers folder to bundle...")
        datas_list.append(('pw-browsers', 'browsers'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'encodings',
        'encodings.utf_8',
        'encodings.latin_1',
        'playwright',
        'playwright.sync_api',
        'playwright.sync_api._context_manager',
        'playwright._impl',
        'playwright._impl._playwright',
        'playwright._impl._browser',
        'playwright._impl._browser_context',
        'playwright._impl._page',
        'playwright._impl._api_structures',
        'playwright._impl._api_types',
        'playwright._impl._connection',
        'playwright._impl._object_factory',
        'playwright._impl._transport',
        'playwright._impl._driver',
        'playwright._impl._helper',
        'greenlet',
        'pyee',
    ],
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
    name='AutoYuPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=target_arch,
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
    name='AutoYuPro',
)

# Use icon.icns if generated (macOS), otherwise fallback to None
icns_path = 'icon.icns'
if not os.path.exists(icns_path):
    icns_path = None

app = BUNDLE(
    coll,
    name='AutoYuPro.app',
    icon=icns_path,
    bundle_identifier='pramana.autoyu.pro',
)
