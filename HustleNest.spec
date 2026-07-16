# -*- mode: python ; coding: utf-8 -*-

import shutil

from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import collect_data_files

node_executable = shutil.which('node.exe')
if not node_executable:
    raise SystemExit('Node.js 22 or later is required to build HustleNest.')
web_datas = [
    ('web\\start-local.mjs', 'web'),
    ('web\\package.json', 'web'),
]


a = Analysis(
    ['hustlenest\\browser_app.py'],
    pathex=[],
    binaries=[(node_executable, 'runtime')],
    datas=[('HustleNest.ico', '.')] + collect_data_files('zipcodes') + web_datas,
    hiddenimports=[
        'requests',
        'hustlenest.services.cloud_sync_service',
        'hustlenest.services.order_service',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
a.datas += Tree('web\\dist', prefix='web\\dist')
a.datas += Tree('web\\node_modules\\vinext', prefix='web\\node_modules\\vinext')
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HustleNest',
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
    icon=['HustleNest.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HustleNest',
)
