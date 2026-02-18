"""Arcade-based UI rendering for Hex Game."""

from __future__ import annotations

from math import cos, hypot, pi, sin

import arcade
from arcade.types import Color, LBWH

from hex_game.config import (
    ICON_PATH_CAPITAL,
    ICON_PATH_DANGER,
    ICON_PATH_FOREST,
    ICON_PATH_MOUNTAIN,
    ICON_PATH_TOWN,
    OWNER_CPU,
    OWNER_PLAYER,
    PHASE_ATTACK,
    PHASE_DEPLOYMENT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TERRAIN_FOREST,
    TERRAIN_MOUNTAIN,
    UI_CAPITAL_ICON_ALPHA,
    UI_CAPITAL_ICON_SIZE_SCALE,
    UI_EDGE_HALF_LENGTH_RATIO,
    UI_EXPOSED_ICON_SIZE_SCALE,
    UI_EXPOSED_ICON_Y_OFFSET_SCALE,
    UI_GRID_LINE_WIDTH_PX,
    UI_MIN_LINE_WIDTH_PX,
    UI_RIVER_LINE_WIDTH_DELTA_PX,
    UI_SELECTED_LINE_WIDTH_EXTRA_PX,
    UI_SELECTION_HIGHLIGHT_SCALE,
    UI_SETTLEMENT_TROOP_Y_OFFSET_SCALE,
    UI_STATUS_SEPARATOR,
    UI_TERRAIN_ICON_SIZE_SCALE,
    UI_TERRAIN_MARKER_Y_OFFSET_SCALE,
    UI_TOWN_ICON_ALPHA,
    UI_TOWN_ICON_SIZE_SCALE,
)
from hex_game.runtime import TextCache, load_font_once
from hex_game.visual import resolve_font_path, resolve_icon_path
from hex_game.visual import (
    COLOR_AMBER,
    COLOR_AQUA,
    COLOR_BRICK_RED,
    COLOR_CHARCOAL,
    COLOR_CORAL,
    COLOR_DEEP_TEAL,
    COLOR_FOG_GRAY,
    COLOR_NEAR_BLACK,
    COLOR_SLATE_GRAY,
    COLOR_SOFT_WHITE,
    COLOR_STEEL_BLUE,
)

_TEXTURE_CACHE: dict[str, arcade.Texture] = {}
_TEXT_CACHE = TextCache(max_entries=4096)
_HEX_GEOMETRY_CACHE: dict[tuple[int, int, int, int], dict[tuple[int, int], dict[str, object]]] = {}


def load_font_spec(font_path_or_file: str, size_px: int, fallback_family: str | None = None) -> dict[str, object]:
    resolved = resolve_font_path(font_path_or_file)
    load_font_once(resolved)
    return {"name": fallback_family or "Roboto", "size": int(size_px)}


def _get_texture(icon_path_or_file: str) -> arcade.Texture:
    resolved = resolve_icon_path(icon_path_or_file)
    texture = _TEXTURE_CACHE.get(resolved)
    if texture is None:
        texture = arcade.load_texture(resolved)
        _TEXTURE_CACHE[resolved] = texture
    return texture


def _icon_entry(icon_path_or_file: str, size_px: int, tint=(255, 255, 255, 255)) -> dict[str, object]:
    return {
        "texture": _get_texture(icon_path_or_file),
        "size": int(size_px),
        "tint": Color(*tint),
    }


def load_icon_assets(hex_radius):
    terrain_size = _scaled_icon_size(hex_radius, UI_TERRAIN_ICON_SIZE_SCALE)
    danger_size = _scaled_icon_size(hex_radius, UI_EXPOSED_ICON_SIZE_SCALE)
    capital_size = _scaled_icon_size(hex_radius, UI_CAPITAL_ICON_SIZE_SCALE)
    town_size = _scaled_icon_size(hex_radius, UI_TOWN_ICON_SIZE_SCALE)
    return {
        "terrain": {
            TERRAIN_FOREST: _icon_entry(ICON_PATH_FOREST, terrain_size),
            TERRAIN_MOUNTAIN: _icon_entry(ICON_PATH_MOUNTAIN, terrain_size),
        },
        "danger": _icon_entry(ICON_PATH_DANGER, danger_size),
        "capital": {
            OWNER_PLAYER: _icon_entry(ICON_PATH_CAPITAL, capital_size, (*COLOR_AQUA, int(UI_CAPITAL_ICON_ALPHA))),
            OWNER_CPU: _icon_entry(ICON_PATH_CAPITAL, capital_size, (*COLOR_CORAL, int(UI_CAPITAL_ICON_ALPHA))),
        },
        "town": {
            OWNER_PLAYER: _icon_entry(ICON_PATH_TOWN, town_size, (*COLOR_AQUA, int(UI_TOWN_ICON_ALPHA))),
            OWNER_CPU: _icon_entry(ICON_PATH_TOWN, town_size, (*COLOR_CORAL, int(UI_TOWN_ICON_ALPHA))),
        },
    }


def draw_frame(window, font_units, font_bar, icon_assets, grid, game):
    window.clear(COLOR_CHARCOAL)
    radius = grid.hex_radius
    line_width = _grid_line_width()
    selected_line_width = max(
        line_width,
        line_width + int(UI_SELECTED_LINE_WIDTH_EXTRA_PX),
    )
    geometry = _get_hex_geometry(grid)
    cells = grid.get_all_cells()

    for cell in cells:
        cell_geometry = geometry[(cell.q, cell.r)]
        x, y = cell_geometry["center"]
        points_arcade = cell_geometry["points_arcade"]
        arcade.draw_polygon_filled(points_arcade, _cell_fill_color(cell))
        _draw_settlement_marker(icon_assets, grid, cell, x, y)
        _draw_terrain_marker(icon_assets, grid, cell, x, y, radius)
        _draw_topology(icon_assets, grid, cell, x, y, radius)

    for cell in cells:
        cell_geometry = geometry[(cell.q, cell.r)]
        x, y = cell_geometry["center"]
        points = cell_geometry["points"]
        points_arcade = cell_geometry["points_arcade"]
        arcade.draw_polygon_outline(points_arcade, COLOR_CHARCOAL, line_width)

        if game.selected_source == (cell.q, cell.r):
            selected = _scaled_hex_points(points, x, y, UI_SELECTION_HIGHLIGHT_SCALE)
            arcade.draw_polygon_outline(_to_arcade_points(selected), COLOR_AMBER, selected_line_width)

        troops = cell.total_troops()
        if troops > 0 and not _is_hidden_from_you(cell):
            text_x, text_y = _troop_text_center(grid, cell, x, y, radius)
            _draw_text(
                str(troops),
                text_x,
                text_y,
                _owner_accent_color(cell.owner),
                int(font_units["size"]),
                str(font_units["name"]),
            )

    _draw_rivers(grid, line_width)
    draw_bottom_bar(font_bar, grid, game)


def draw_bottom_bar(font, grid, game):
    player_text = "You" if game.active_player == OWNER_PLAYER else "CPU"
    active_player_color = COLOR_AQUA if game.active_player == OWNER_PLAYER else COLOR_CORAL
    player_area, cpu_area = grid.count_control()
    arcade.draw_lbwh_rectangle_filled(0, 0, SCREEN_WIDTH, grid.bottom_bar_height, COLOR_NEAR_BLACK)

    separator = UI_STATUS_SEPARATOR if UI_STATUS_SEPARATOR else " / "
    segments = [
        (f"L: {game.level}", COLOR_SOFT_WHITE),
        (separator, COLOR_SOFT_WHITE),
        (f"T: {game.turn}", COLOR_SOFT_WHITE),
        (separator, COLOR_SOFT_WHITE),
        (player_text, active_player_color),
        (separator, COLOR_SOFT_WHITE),
        (_phase_status_text(game), COLOR_SOFT_WHITE),
        (separator, COLOR_SOFT_WHITE),
        (f"{player_area}", COLOR_AQUA),
        (separator, COLOR_SOFT_WHITE),
        (f"{cpu_area}", COLOR_CORAL),
    ]
    _draw_centered_status_segments(
        segments=segments,
        font_name=str(font["name"]),
        font_size=int(font["size"]),
        bar_height=grid.bottom_bar_height,
    )


def _draw_centered_status_segments(segments, font_name: str, font_size: int, bar_height: int):
    if not segments:
        return

    text_objects = []
    total_width = 0.0
    for text, color in segments:
        text_obj = _TEXT_CACHE.get_text(
            text=text,
            color=color,
            font_size=font_size,
            font_name=font_name,
            anchor_x="left",
            anchor_y="center",
        )
        text_objects.append(text_obj)
        total_width += float(text_obj.content_width)

    cursor_x = (SCREEN_WIDTH - total_width) / 2.0
    center_y = bar_height / 2.0
    for text_obj in text_objects:
        text_obj.x = cursor_x
        text_obj.y = center_y
        text_obj.draw()
        cursor_x += float(text_obj.content_width)


def get_cell_under_pixel(grid, px, py):
    geometry = _get_hex_geometry(grid)
    for cell in grid.get_all_cells():
        points = geometry[(cell.q, cell.r)]["points"]
        if _point_in_polygon((px, py), points):
            return cell
    return None


def _phase_status_text(game):
    if getattr(game, "game_over", False):
        if getattr(game, "campaign_won", False):
            return "Campaign Won"
        return "Game Over"
    if game.phase == PHASE_DEPLOYMENT:
        if hasattr(game, "deploy_units_total") and hasattr(game, "deploy_units_remaining"):
            used = game.deploy_units_total - game.deploy_units_remaining
            return f"Deploy {used}/{game.deploy_units_total}"
        used = game.deploy_chunks_total - game.deploy_chunks_remaining
        return f"Deploy {used}/{game.deploy_chunks_total}"
    if game.phase == PHASE_ATTACK:
        return f"Attack {game.attacks_used}"
    return "Move"


def _draw_rivers(grid, grid_line_width):
    river_line_width = max(
        int(UI_MIN_LINE_WIDTH_PX),
        grid_line_width + int(UI_RIVER_LINE_WIDTH_DELTA_PX),
    )
    _draw_edge_segments(grid, grid.river_edges, COLOR_STEEL_BLUE, river_line_width)


def _draw_edge_segments(grid, edges, color, line_width):
    radius = grid.hex_radius
    half_edge = radius * UI_EDGE_HALF_LENGTH_RATIO
    for edge in edges:
        (q1, r1), (q2, r2) = edge
        x1, y1 = grid.axial_to_pixel(q1, r1)
        x2, y2 = grid.axial_to_pixel(q2, r2)

        dx = x2 - x1
        dy = y2 - y1
        dist = hypot(dx, dy)
        if dist == 0:
            continue

        nx = -dy / dist
        ny = dx / dist
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2

        p1 = (mx + nx * half_edge, my + ny * half_edge)
        p2 = (mx - nx * half_edge, my - ny * half_edge)
        arcade.draw_line(p1[0], _to_arcade_y(p1[1]), p2[0], _to_arcade_y(p2[1]), color, line_width)


def _draw_terrain_marker(icon_assets, grid, cell, x, y, radius):
    if grid.is_town_coord(cell.q, cell.r):
        return
    icon = icon_assets["terrain"].get(cell.terrain)
    if icon is None:
        return

    marker_y = y + radius * UI_TERRAIN_MARKER_Y_OFFSET_SCALE
    _draw_icon(icon, x, marker_y)


def _draw_settlement_marker(icon_assets, grid, cell, x, y):
    if not grid.is_town_coord(cell.q, cell.r):
        return
    if grid.is_capital_coord(cell.q, cell.r):
        icon = icon_assets["capital"].get(cell.owner)
    else:
        icon = icon_assets["town"].get(cell.owner)
    if icon is None:
        return
    _draw_icon(icon, x, y)


def _draw_topology(icon_assets, grid, cell, x, y, radius):
    if grid.frontline_topology(cell.q, cell.r) == "exposed":
        _draw_exposed_icon(icon_assets.get("danger"), x, y, radius)


def _draw_exposed_icon(icon, x, y, radius):
    if icon is None:
        return
    icon_y = y - radius * UI_EXPOSED_ICON_Y_OFFSET_SCALE
    _draw_icon(icon, x, icon_y)


def _draw_icon(icon_entry, center_x: float, center_y: float):
    size = int(icon_entry["size"])
    left = center_x - size / 2
    bottom = _to_arcade_y(center_y) - size / 2
    arcade.draw_texture_rect(
        icon_entry["texture"],
        LBWH(left, bottom, size, size),
        color=icon_entry["tint"],
    )


def _draw_text(text: str, x: float, y: float, color, size: int, font_name: str):
    _TEXT_CACHE.draw(
        text=text,
        x=x,
        y=_to_arcade_y(y),
        color=color,
        font_size=size,
        font_name=font_name,
        anchor_x="center",
        anchor_y="center",
    )


def _to_arcade_y(y_top: float) -> float:
    return SCREEN_HEIGHT - y_top


def _to_arcade_points(points):
    return [(px, _to_arcade_y(py)) for px, py in points]


def _point_in_polygon(point, polygon):
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside
    return inside


def _get_hex_geometry(grid):
    key = (id(grid), int(grid.cols), int(grid.rows), int(grid.hex_radius))
    cached = _HEX_GEOMETRY_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_HEX_GEOMETRY_CACHE) > 8:
        _HEX_GEOMETRY_CACHE.clear()

    radius = grid.hex_radius
    geometry: dict[tuple[int, int], dict[str, object]] = {}
    for cell in grid.get_all_cells():
        x, y = grid.axial_to_pixel(cell.q, cell.r)
        points = tuple(
            (x + radius * cos(pi / 180 * (60 * i)), y + radius * sin(pi / 180 * (60 * i)))
            for i in range(6)
        )
        geometry[(cell.q, cell.r)] = {
            "center": (x, y),
            "points": points,
            "points_arcade": _to_arcade_points(points),
        }

    _HEX_GEOMETRY_CACHE[key] = geometry
    return geometry


def _scaled_hex_points(base_points, x, y, scale):
    return [(x + (px - x) * scale, y + (py - y) * scale) for px, py in base_points]


def _grid_line_width():
    return max(int(UI_MIN_LINE_WIDTH_PX), int(UI_GRID_LINE_WIDTH_PX))


def _cell_fill_color(cell):
    if cell.owner == OWNER_PLAYER:
        return COLOR_DEEP_TEAL
    if cell.owner == OWNER_CPU:
        return COLOR_BRICK_RED
    return COLOR_SLATE_GRAY


def _owner_accent_color(owner):
    if owner == OWNER_PLAYER:
        return COLOR_AQUA
    if owner == OWNER_CPU:
        return COLOR_CORAL
    return COLOR_FOG_GRAY


def _is_hidden_from_you(cell):
    return cell.owner == OWNER_CPU and cell.terrain == TERRAIN_FOREST


def _troop_text_center(grid, cell, x, y, radius):
    if grid.is_town_coord(cell.q, cell.r):
        return x, y + radius * UI_SETTLEMENT_TROOP_Y_OFFSET_SCALE
    return x, y


def _scaled_icon_size(radius, scale):
    return max(12, int(round(radius * scale)))


# Backward-compatible alias while call sites migrate.
draw = draw_frame

