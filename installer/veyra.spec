# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification for VEYRA Desktop Application.
Packages all core subsystems, UI, collectors, analyzers, diagnostics,
and locked branding assets while strictly excluding test/simulation data (Rule 9).
"""
import os
import sys
from pathlib import Path

block_cipher = None

project_root = Path(SPECPATH).parent.resolve()
assets_dir = project_root / "assets" / "branding"
icon_path = str(assets_dir / "normal" / "VEYRA_Normal_Icon.ico")

# Collect branding assets recursively
datas = [
    (str(assets_dir), "assets/branding"),
]

# Hidden imports required by dynamic loaders or standard library reflection
hiddenimports = [
    "psutil",
    "sqlite3",
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "app.core.branding",
    "app.core.config",
    "app.core.contracts",
    "app.core.exceptions",
    "app.core.logging",
    "app.core.paths",
    "app.core.privilege",
    "app.core.security",
    "app.core.supervisor",
    "app.core.time",
    "app.api.server",
    "app.ui.app",
    "app.ui.theme",
    "app.ui.state",
    "collectors.coordinator",
    "collectors.common",
    "collectors.system",
    "collectors.network",
    "collectors.wifi",
    "collectors.gpu",
    "collectors.connectivity",
    "analyzer.contracts",
    "analyzer.engine",
    "analyzer.thresholds",
    "analyzer.incidents",
    "analyzer.bottleneck",
    "analyzer.gaming",
    "analyzer.ai.ask_veyra",
    "storage.engine",
    "storage.sqlite_engine",
    "storage.migrations.migration_manager",
    "diagnostics.investigator",
    "diagnostics.probes",
    "diagnostics.runner",
    "optimization.executor",
    "optimization.snapshots",
    "optimization.verification",
]

# RULE 9: Strictly exclude simulation framework and test suites from production package
excludes = [
    "simulation",
    "tests",
    "unittest",
    "pytest",
]

a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name="VEYRA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Windowed GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VEYRA",
)
