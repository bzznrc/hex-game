"""Generic layout helpers for odd-q vertical hex boards."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class HexGridLayout:
    """Resolved screen-fit layout for an odd-q vertical hex grid."""

    columns: int
    rows: int
    radius_px: int
    origin_x_px: int
    origin_y_px: int
    bottom_bar_height_px: int

    def as_tuple(self) -> tuple[int, int, int, int, int, int]:
        """Return constructor-friendly tuple ordering."""

        return (
            self.columns,
            self.rows,
            self.radius_px,
            self.origin_x_px,
            self.origin_y_px,
            self.bottom_bar_height_px,
        )


def board_width_px(columns: int, radius_px: float) -> float:
    """Pixel width of an odd-q vertical hex board."""

    return radius_px * (1.5 * (columns - 1) + 2)


def board_height_px(columns: int, rows: int, radius_px: float) -> float:
    """Pixel height of an odd-q vertical hex board."""

    odd_offset = 0.5 if columns > 1 else 0.0
    return radius_px * ((rows - 1 + odd_offset) * math.sqrt(3) + 2)


def axial_to_pixel_odd_q(
    q: int,
    r: int,
    radius_px: float,
    origin_x_px: float,
    origin_y_px: float,
) -> tuple[float, float]:
    """Map odd-q offset axial coordinates to pixel center coordinates."""

    x = origin_x_px + radius_px * (1.5 * q + 1)
    if q % 2 == 0:
        y = origin_y_px + radius_px + r * (math.sqrt(3) * radius_px)
    else:
        y = origin_y_px + radius_px + (r + 0.5) * (math.sqrt(3) * radius_px)
    return x, y


def neighbor_coords_odd_q(q: int, r: int) -> list[tuple[int, int]]:
    """Return six odd-q neighbor coordinates without bounds filtering."""

    if q % 2 == 0:
        deltas = [(1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (0, 1)]
    else:
        deltas = [(1, 1), (1, 0), (0, -1), (-1, 0), (-1, 1), (0, 1)]
    return [(q + dq, r + dr) for dq, dr in deltas]


def compute_best_fit_hex_layout(
    screen_width_px: int,
    screen_height_px: int,
    bottom_bar_height_px: int,
    target_hex_count: int,
    min_radius_px: int = 6,
    min_columns: int = 2,
    min_rows: int = 1,
    fallback: tuple[int, int, int] = (2, 1, 20),
) -> HexGridLayout:
    """Compute a best-fit even-area odd-q board layout for a target tile count."""

    available_width = int(screen_width_px)
    available_height = int(screen_height_px) - int(bottom_bar_height_px)
    if available_width < 1 or available_height < 1:
        raise ValueError("screen dimensions must leave positive playable area")

    target_tiles = max(2, int(target_hex_count))
    if target_tiles % 2 != 0:
        target_tiles -= 1

    best: tuple[int, int, int] | None = None
    best_score: tuple[float, float, float, float] | None = None
    target_aspect = available_width / max(1, available_height)

    max_cols = max(int(min_columns), int(math.sqrt(target_tiles * target_aspect) * 2) + 6)
    max_rows = max(int(min_rows), int(math.sqrt(target_tiles / max(target_aspect, 0.1)) * 2) + 6)

    for columns in range(int(min_columns), max_cols + 1):
        for rows in range(int(min_rows), max_rows + 1):
            area = columns * rows
            if area % 2 != 0:
                continue

            radius_by_width = available_width / (1.5 * (columns - 1) + 2)
            odd_offset = 0.5 if columns > 1 else 0.0
            radius_by_height = available_height / (((rows - 1 + odd_offset) * math.sqrt(3)) + 2)
            radius = int(min(radius_by_width, radius_by_height))
            if radius < int(min_radius_px):
                continue

            diff_tiles = abs(area - target_tiles)
            diff_aspect = abs((columns / rows) - target_aspect)
            score = (diff_tiles, -radius, diff_aspect, -area)

            if best is None or score < best_score:
                best = (columns, rows, radius)
                best_score = score

    if best is None:
        columns, rows, radius = fallback
    else:
        columns, rows, radius = best

    width = board_width_px(columns, radius)
    height = board_height_px(columns, rows, radius)
    origin_x = int((available_width - width) / 2)
    origin_y = int((available_height - height) / 2)

    return HexGridLayout(
        columns=columns,
        rows=rows,
        radius_px=radius,
        origin_x_px=origin_x,
        origin_y_px=origin_y,
        bottom_bar_height_px=int(bottom_bar_height_px),
    )


__all__ = [
    "HexGridLayout",
    "board_width_px",
    "board_height_px",
    "axial_to_pixel_odd_q",
    "neighbor_coords_odd_q",
    "compute_best_fit_hex_layout",
]
