import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ["TRAILBUDDY_SETTINGS_APP"] = "AnalyzerTests"  # keep the user's real preferences untouched
