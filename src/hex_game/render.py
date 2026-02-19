"""Arcade-based UI rendering for Hex Game."""

from __future__ import annotations

from math import cos, hypot, pi, sin

import arcade
from arcade.types import Color, LBWH

from hex_game.config import (
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
    ICON_PATH_CAPITAL,
    ICON_PATH_DANGER,
    ICON_PATH_FOREST,
    ICON_PATH_MOUNTAIN,
    ICON_PATH_TOWN,
    MAX_MOVEMENT_SOURCE_HEXES,
    OWNER_CPU,
    OWNER_PLAYER,
    PHASE_ATTACK,
    PHASE_DEPLOYMENT,
    PHASE_MOVEMENT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TERRAIN_FOREST,
    TERRAIN_MOUNTAIN,
    TROOP_CAP_MOUNTAIN,
    TROOP_CAP_PLAIN_FOREST,
    TROOP_CAP_TOWN,
    UI_FEATURE_ICON_ALPHA,
    UI_CAPITAL_ICON_SIZE_SCALE,
    UI_EDGE_HALF_LENGTH_RATIO,
    UI_EXPOSED_ICON_SIZE_SCALE,
    UI_EXPOSED_ICON_Y_OFFSET_SCALE,
    UI_GRID_LINE_WIDTH_PX,
    UI_MIN_LINE_WIDTH_PX,
    UI_RIVER_LINE_WIDTH_DELTA_PX,
    UI_SELECTED_LINE_WIDTH_EXTRA_PX,
    UI_SELECTION_HIGHLIGHT_SCALE,
    UI_STATUS_SEPARATOR,
    UI_TERRAIN_ICON_SIZE_SCALE,
    UI_TROOP_DOT_OUTLINE_WIDTH_SCALE,
    UI_TROOP_DOT_RADIUS_SCALE,
    UI_TROOP_DOT_SEGMENTS,
    UI_TROOP_LAYOUT_SCALE,
    UI_TOWN_ICON_SIZE_SCALE,
)
from hex_game.assets import resolve_font_path, resolve_icon_path
from hex_game.runtime import TextCache, load_font_once

_TEXTURE_CACHE: dict[str, arcade.Texture] = {}
_TEXT_CACHE = TextCache(max_entries=4096)
_HEX_GEOMETRY_CACHE: dict[tuple[int, int, int, int], dict[tuple[int, int], dict[str, object]]] = {}
_TROOP_DOT_MIN_RADIUS_PX = 2.0
_TROOP_DOT_OUTLINE_MIN_WIDTH_PX = 1
_TROOP_DOT_OUTLINE_ALPHA = 220
_TROOP_TRIANGLE_GROUP_SIZE = 3
_TROOP_TRIANGLE_DX_FROM_DOT_SCALE = 2.18
_TROOP_TRIANGLE_DY_FROM_DOT_SCALE = 1.95
_TROOP_GROUP_STEP_FROM_DX_SCALE = 1.50
_TROOP_TRIANGLE_DX_RADIUS_SCALE = 0.195
_TROOP_TRIANGLE_DY_RADIUS_SCALE = 0.185
_TROOP_GROUP_STEP_RADIUS_SCALE = 0.43


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
            TERRAIN_FOREST: _icon_entry(ICON_PATH_FOREST, terrain_size, (*COLOR_SOFT_WHITE, int(UI_FEATURE_ICON_ALPHA))),
            TERRAIN_MOUNTAIN: _icon_entry(
                ICON_PATH_MOUNTAIN, terrain_size, (*COLOR_SOFT_WHITE, int(UI_FEATURE_ICON_ALPHA))
            ),
        },
        "danger": _icon_entry(ICON_PATH_DANGER, danger_size),
        "capital": {
            OWNER_PLAYER: _icon_entry(ICON_PATH_CAPITAL, capital_size, (*COLOR_AQUA, int(UI_FEATURE_ICON_ALPHA))),
            OWNER_CPU: _icon_entry(ICON_PATH_CAPITAL, capital_size, (*COLOR_CORAL, int(UI_FEATURE_ICON_ALPHA))),
        },
        "town": {
            OWNER_PLAYER: _icon_entry(ICON_PATH_TOWN, town_size, (*COLOR_AQUA, int(UI_FEATURE_ICON_ALPHA))),
            OWNER_CPU: _icon_entry(ICON_PATH_TOWN, town_size, (*COLOR_CORAL, int(UI_FEATURE_ICON_ALPHA))),
        },
    }


def draw_frame(window, font_bar, icon_assets, grid, game):
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

        if not _is_hidden_from_you(cell):
            _draw_troop_markers(grid, cell, x, y, radius)

    _draw_rivers(grid, line_width)
    draw_bottom_bar(font_bar, grid, game)


def draw_bottom_bar(font, grid, game):
    player_text = "You" if game.active_player == OWNER_PLAYER else "CPU"
    active_player_color = COLOR_AQUA if game.active_player == OWNER_PLAYER else COLOR_CORAL
    player_area, cpu_area = grid.count_control()
    arcade.draw_lbwh_rectangle_filled(
        0,
        0,
        SCREEN_WIDTH,
        grid.bottom_bar_height,
        COLOR_NEAR_BLACK,
    )

    separator = UI_STATUS_SEPARATOR if UI_STATUS_SEPARATOR else " / "
    action_status = _phase_status_text(game)
    segments = [
        (f"L: {game.level}", COLOR_SOFT_WHITE),
        (separator, COLOR_SOFT_WHITE),
        (f"T: {game.turn}", COLOR_SOFT_WHITE),
        (separator, COLOR_SOFT_WHITE),
        (player_text, active_player_color),
        (separator, COLOR_SOFT_WHITE),
        (action_status, COLOR_SOFT_WHITE),
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
        return "Campaign Won" if getattr(game, "campaign_won", False) else "Game Over"

    if game.phase == PHASE_DEPLOYMENT:
        deploy_remaining = int(getattr(game, "deploy_units_remaining", 0))
        deploy_total = int(getattr(game, "deploy_units_total", 0))
        return f"Deploy: {deploy_remaining}/{deploy_total}"

    if game.phase == PHASE_ATTACK:
        return "Attack"

    if game.phase == PHASE_MOVEMENT:
        move_used = len(getattr(game, "movement_sources_used", ()))
        return f"Move: {move_used}/{int(MAX_MOVEMENT_SOURCE_HEXES)}"

    return str(game.phase)


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

    _draw_bottom_anchored_icon(icon, x, _hex_bottom_y(y, radius))


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


def _hex_bottom_y(y: float, radius: float) -> float:
    return y + radius


def _draw_icon(icon_entry, center_x: float, center_y: float):
    size = int(icon_entry["size"])
    left = center_x - size / 2
    bottom = _to_arcade_y(center_y) - size / 2
    arcade.draw_texture_rect(
        icon_entry["texture"],
        LBWH(left, bottom, size, size),
        color=icon_entry["tint"],
    )


def _draw_bottom_anchored_icon(icon_entry, center_x: float, bottom_y: float):
    size = int(icon_entry["size"])
    left = center_x - size / 2
    bottom = _to_arcade_y(bottom_y)
    arcade.draw_texture_rect(
        icon_entry["texture"],
        LBWH(left, bottom, size, size),
        color=icon_entry["tint"],
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


def _draw_troop_markers(grid, cell, center_x: float, center_y: float, radius: float):
    display_cap = _display_troop_cap(grid, cell)
    troops = min(max(0, int(cell.total_troops())), display_cap)
    if troops <= 0:
        return

    dot_radius = max(_TROOP_DOT_MIN_RADIUS_PX, radius * float(UI_TROOP_DOT_RADIUS_SCALE))
    dot_positions = _troop_dot_layout(center_x, center_y, radius, display_cap, dot_radius)
    filled_color = _owner_accent_color(cell.owner)
    outline_width = max(
        _TROOP_DOT_OUTLINE_MIN_WIDTH_PX,
        int(round(dot_radius * float(UI_TROOP_DOT_OUTLINE_WIDTH_SCALE))),
    )
    dot_segments = int(UI_TROOP_DOT_SEGMENTS)

    for index, (dot_x, dot_y) in enumerate(dot_positions):
        if index >= troops:
            continue
        arcade_y = _to_arcade_y(dot_y)
        arcade.draw_circle_filled(dot_x, arcade_y, dot_radius, filled_color, num_segments=dot_segments)
        arcade.draw_circle_outline(
            dot_x,
            arcade_y,
            dot_radius,
            (*COLOR_CHARCOAL, _TROOP_DOT_OUTLINE_ALPHA),
            border_width=outline_width,
            num_segments=dot_segments,
        )


def _display_troop_cap(grid, cell) -> int:
    cap = int(grid.troop_cap_at(cell.q, cell.r))
    if cap <= int(TROOP_CAP_MOUNTAIN):
        return int(TROOP_CAP_MOUNTAIN)
    if cap <= int(TROOP_CAP_PLAIN_FOREST):
        return int(TROOP_CAP_PLAIN_FOREST)
    return int(TROOP_CAP_TOWN)


def _troop_dot_layout(center_x: float, center_y: float, hex_radius: float, display_cap: int, dot_radius: float):
    groups = max(1, int(display_cap) // _TROOP_TRIANGLE_GROUP_SIZE)
    layout_scale = float(UI_TROOP_LAYOUT_SCALE)
    triangle_dx = max(
        dot_radius * _TROOP_TRIANGLE_DX_FROM_DOT_SCALE,
        hex_radius * _TROOP_TRIANGLE_DX_RADIUS_SCALE * layout_scale,
    )
    triangle_dy = max(
        dot_radius * _TROOP_TRIANGLE_DY_FROM_DOT_SCALE,
        hex_radius * _TROOP_TRIANGLE_DY_RADIUS_SCALE * layout_scale,
    )
    group_step = max(
        triangle_dx * _TROOP_GROUP_STEP_FROM_DX_SCALE,
        hex_radius * _TROOP_GROUP_STEP_RADIUS_SCALE * layout_scale,
    )
    first_group_center_x = center_x - ((groups - 1) * group_step) / 2.0

    positions: list[tuple[float, float]] = []
    for group_index in range(groups):
        group_center_x = first_group_center_x + group_index * group_step
        upside_down = groups > 1 and group_index % 2 == 0
        positions.extend(_triangle_dot_positions(group_center_x, center_y, triangle_dx, triangle_dy, upside_down))

    return positions


def _triangle_dot_positions(
    center_x: float,
    center_y: float,
    triangle_dx: float,
    triangle_dy: float,
    upside_down: bool,
):
    if upside_down:
        offsets = (
            (-triangle_dx / 2.0, -triangle_dy / 2.0),
            (triangle_dx / 2.0, -triangle_dy / 2.0),
            (0.0, triangle_dy / 2.0),
        )
    else:
        offsets = (
            (-triangle_dx / 2.0, triangle_dy / 2.0),
            (triangle_dx / 2.0, triangle_dy / 2.0),
            (0.0, -triangle_dy / 2.0),
        )

    return [(center_x + dx, center_y + dy) for dx, dy in offsets]


def _scaled_icon_size(radius, scale):
    return max(12, int(round(radius * scale)))

