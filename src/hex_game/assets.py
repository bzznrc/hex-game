"""Asset path resolution for local package assets."""

from __future__ import annotations

from pathlib import Path


_ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def resolve_asset_path(relative_path: str) -> str:
    raw_path = Path(relative_path)
    if raw_path.is_absolute() and raw_path.exists():
        return str(raw_path)

    normalized = relative_path.replace("\\", "/")
    return str(_ASSETS_DIR / normalized)


def resolve_font_path(font_path_or_file: str) -> str:
    normalized = font_path_or_file.replace("\\", "/")
    if "/" not in normalized:
        normalized = f"fonts/{normalized}"
    return resolve_asset_path(normalized)


def resolve_icon_path(icon_path_or_file: str) -> str:
    normalized = icon_path_or_file.replace("\\", "/")
    if "/" not in normalized:
        normalized = f"icons/{normalized}"
    return resolve_asset_path(normalized)
