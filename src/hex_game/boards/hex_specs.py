"""Hex-grid board presets and rendering tuning."""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class HexBoardSpec:
    """Configuration for a board made of hexagonal cells."""

    screen_width_px: int
    screen_height_px: int
    bottom_bar_height_px: int
    target_hex_count: int


@dataclass(frozen=True)
class HexRenderSpec:
    """Rendering and asset tuning for hex-cell interfaces."""

    selection_highlight_scale: float
    min_line_width_px: int
    grid_line_width_px: int
    selected_line_width_extra_px: int
    adjacency_edge_line_width_delta_px: int
    edge_half_length_ratio: float
    cell_overlay_y_offset_scale: float
    cell_overlay_icon_size_scale: float
    top_overlay_y_offset_scale: float
    top_overlay_icon_size_scale: float
    center_primary_icon_size_scale: float
    center_primary_icon_alpha: int
    center_secondary_icon_size_scale: float
    center_secondary_icon_alpha: int
    center_label_y_offset_scale: float


HEX_BOARD_STANDARD: Final[HexBoardSpec] = HexBoardSpec(
    screen_width_px=800,
    screen_height_px=800,
    bottom_bar_height_px=36,
    target_hex_count=80,
)

HEX_RENDER_STANDARD: Final[HexRenderSpec] = HexRenderSpec(
    selection_highlight_scale=0.90,
    min_line_width_px=2,
    grid_line_width_px=4,
    selected_line_width_extra_px=1,
    adjacency_edge_line_width_delta_px=-1,
    edge_half_length_ratio=0.50,
    cell_overlay_y_offset_scale=0.62,
    cell_overlay_icon_size_scale=0.42,
    top_overlay_y_offset_scale=0.62,
    top_overlay_icon_size_scale=0.28,
    center_primary_icon_size_scale=1.35,
    center_primary_icon_alpha=128,
    center_secondary_icon_size_scale=1.35,
    center_secondary_icon_alpha=128,
    center_label_y_offset_scale=0.14,
)

__all__ = [
    "HexBoardSpec",
    "HexRenderSpec",
    "HEX_BOARD_STANDARD",
    "HEX_RENDER_STANDARD",
]
