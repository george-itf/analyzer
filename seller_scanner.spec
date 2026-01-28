# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Seller Opportunity Scanner."""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('fixtures', 'fixtures'),
        ('migrations', 'migrations'),
        ('alembic.ini', '.'),
    ],
    hiddenimports=[
        'sqlalchemy.dialects.sqlite',
        'PyQt6.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Seller Opportunity Scanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Seller Opportunity Scanner',
)

app = BUNDLE(
    coll,
    name='Seller Opportunity Scanner.app',
    icon=None,
    bundle_identifier='com.sellertools.opportunity-scanner',
    info_plist={
        'CFBundleName': 'Seller Opportunity Scanner',
        'CFBundleDisplayName': 'Seller Opportunity Scanner',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '13.0',
        'NSRequiresAquaSystemAppearance': False,
    },
)
