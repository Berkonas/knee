# PyInstaller spec for standalone builds:  uv run pyinstaller packaging/trailbuddy.spec --noconfirm
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).parent
datas = [(str(ROOT / "assets"), "assets")]
models = list((ROOT / "models").glob("*.task"))
if models:
    datas.append((str(ROOT / "models"), "models"))
datas += collect_data_files("mediapipe")
datas += collect_data_files("imageio_ffmpeg")
binaries = collect_dynamic_libs("mediapipe")

a = Analysis([str(ROOT / "packaging" / "launch.py")], pathex=[str(ROOT / "src")], binaries=binaries, datas=datas,
             hiddenimports=["trailbuddy", "openpyxl", "matplotlib.backends.backend_qtagg"],
             excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore"])
pyz = PYZ(a.pure)
icon = str(ROOT / "assets" / ("icon.icns" if sys.platform == "darwin" else "icon.ico"))
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="TrailBuddy Analyzer", console=False, icon=icon)
coll = COLLECT(exe, a.binaries, a.datas, name="TrailBuddy Analyzer")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="TrailBuddy Analyzer.app", icon=icon, bundle_identifier="edu.classproject.trailbuddy-analyzer",
                 info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "1.0.0"})
