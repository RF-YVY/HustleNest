from __future__ import annotations

import sys
from pathlib import Path


def resolve_asset_path(name: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    candidate = base_path / name
    if candidate.exists():
        return candidate
    return Path(__file__).resolve().parent / name


def get_app_icon_path() -> Path:
    return resolve_asset_path("WickerMadeSales.ico")
