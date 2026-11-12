"""Locations for bundled resources and the downloaded pose model."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[3]  # repository root


def assets_dir() -> Path:
    return resource_root() / "assets"


def user_data_dir() -> Path:
    """Per-user folder used only by packaged builds (source checkouts keep models in ./models)."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "TrailBuddy Analyzer"


def models_dir() -> Path:
    bundled = resource_root() / "models"
    if not is_frozen():
        return bundled
    return bundled if any(bundled.glob("*.task")) else user_data_dir() / "models"
