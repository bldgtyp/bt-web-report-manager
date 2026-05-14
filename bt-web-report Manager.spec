# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from pathlib import Path

_nicegui_spec = importlib.util.find_spec("nicegui")
if _nicegui_spec is None or _nicegui_spec.origin is None:
    raise RuntimeError("nicegui must be importable in the build environment")
_nicegui_dir = str(Path(_nicegui_spec.origin).parent)

a = Analysis(
    ['src/bt_web_report_manager/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[(_nicegui_dir, 'nicegui')],
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
    [],
    exclude_binaries=True,
    name='bt-web-report Manager',
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
    icon=['resources/icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='bt-web-report Manager',
)
app = BUNDLE(
    coll,
    name='bt-web-report Manager.app',
    icon='resources/icon.icns',
    bundle_identifier=None,
)
