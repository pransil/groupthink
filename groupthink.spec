# groupthink.spec — PyInstaller build spec for Mac and Windows.
#
# Run from the *parent* directory of the groupthink/ repo:
#
#   pip install pyinstaller
#   pyinstaller groupthink/groupthink.spec
#
# Outputs:
#   Mac:     dist/Groupthink.app  (wrap in DMG for distribution)
#   Windows: dist/Groupthink.exe  (single file)

import sys
import os

# SPECPATH is the directory containing this file (the repo/package root).
# Its parent is needed so "from groupthink.xxx import ..." resolves correctly.
_parent = os.path.dirname(SPECPATH)

block_cipher = None

a = Analysis(
    [os.path.join(SPECPATH, "main.py")],
    pathex=[_parent],
    binaries=[],
    datas=[],
    hiddenimports=[
        "anthropic",
        "anthropic.types",
        "openai",
        "google.genai",
        "google.genai.types",
        "tavily",
        "aiofiles",
        "qasync",
        "dotenv",
        "PyQt6",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "groupthink.core.topic_manager",
        "groupthink.core.llm_router",
        "groupthink.core.groupthink",
        "groupthink.core.web_search",
        "groupthink.core.session_manager",
        "groupthink.core.app_settings",
        "groupthink.core.cost_tracker",
        "groupthink.gui.main_window",
        "groupthink.gui.topic_panel",
        "groupthink.gui.iteration_view",
        "groupthink.gui.markdown_renderer",
        "groupthink.gui.settings_dialog",
        "groupthink.gui.theme",
        "groupthink.gui.icon",
        "groupthink.gui.cost_widget",
        "groupthink.gui.settings_dialog",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == "darwin":
    # One-directory build wrapped in a .app bundle for macOS
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="Groupthink",
        debug=False,
        strip=False,
        upx=False,
        console=False,
        argv_emulation=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        name="Groupthink",
    )
    app = BUNDLE(
        coll,
        name="Groupthink.app",
        bundle_identifier="com.groupthink.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleName": "Groupthink",
            "NSRequiresAquaSystemAppearance": False,
        },
    )

else:
    # Single-file .exe for Windows
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="Groupthink",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
    )
