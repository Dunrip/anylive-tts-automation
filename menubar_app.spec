# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AnyLive TTS Menu Bar App (rumps-based)
"""

block_cipher = None

a = Analysis(
    ['menubar_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('configs/default.json', 'configs'),
        ('configs/template.json', 'configs'),
        ('configs/test_template.csv', 'configs'),
    ],
    hiddenimports=[
        'rumps',
        'playwright',
        'playwright.async_api',
        'playwright.sync_api',
        'pandas',
        'queue',
        'asyncio',
        'threading',
        'json',
        'logging',
        'subprocess',
        'auto_tts',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='AnyLiveTTS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
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
    name='AnyLiveTTS',
)

app = BUNDLE(
    coll,
    name='AnyLiveTTS.app',
    icon=None,
    bundle_identifier='com.anylive.tts.menubar',
    info_plist={
        'CFBundleName': 'AnyLive TTS',
        'CFBundleDisplayName': 'AnyLive TTS Automation',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSUIElement': True,
        # Ensure an AppKit principal class exists for proper Cocoa integration
        'NSPrincipalClass': 'NSApplication',
        'NSAppleEventsUsageDescription': 'AnyLive TTS needs to automate browser tasks.',
    },
)
