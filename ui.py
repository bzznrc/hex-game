import os
import pygame
from math import pi, cos, sin, hypot
from constants import *


_ICON_CACHE = {}
_TINTED_ICON_CACHE = {}


def load_icon_assets(hex_radius, base_dir):
    terrain_size = _scaled_icon_size(hex_radius, UI_TERRAIN_ICON_SIZE_SCALE)
    danger_size = _scaled_icon_size(hex_radius, UI_EXPOSED_ICON_SIZE_SCALE)
    capital_size = _scaled_icon_size(hex_radius, UI_CAPITAL_ICON_SIZE_SCALE)
    town_size = _scaled_icon_size(hex_radius, UI_TOWN_ICON_SIZE_SCALE)
    capital_path = os.path.join(base_dir, ICON_PATH_CAPITAL)
    town_path = os.path.join(base_dir, ICON_PATH_TOWN)
    return {
        "terrain": {
            TERRAIN_FOREST: _load_icon(os.path.join(base_dir, ICON_PATH_FOREST), terrain_size),
            TERRAIN_MOUNTAIN: _load_icon(os.path.join(base_dir, ICON_PATH_MOUNTAIN), terrain_size),
        },
        "danger": _load_icon(os.path.join(base_dir, ICON_PATH_DANGER), danger_size),
        "capital": {
            OWNER_PLAYER: _load_tinted_icon(capital_path, capital_size, COLOR_P1_LIGHT, UI_CAPITAL_ICON_ALPHA),
            OWNER_CPU: _load_tinted_icon(capital_path, capital_size, COLOR_P2_LIGHT, UI_CAPITAL_ICON_ALPHA),
        },
        "town": {
            OWNER_PLAYER: _load_tinted_icon(town_path, town_size, COLOR_P1_LIGHT, UI_TOWN_ICON_ALPHA),
            OWNER_CPU: _load_tinted_icon(town_path, town_size, COLOR_P2_LIGHT, UI_TOWN_ICON_ALPHA),
        },
    }


def draw(surface, font_units, font_bar, icon_assets, grid, game):
    surface.fill(COLOR_BACKGROUND)
    cache = {}
    radius = grid.hex_radius
    line_width = _grid_line_width()
    selected_line_width = max(
        line_width,
        line_width + int(UI_SELECTED_LINE_WIDTH_EXTRA_PX),
    )

    for cell in grid.get_all_cells():
        x, y = grid.axial_to_pixel(cell.q, cell.r)
        points = _hex_points(cache, x, y, radius)
        pygame.draw.polygon(surface, _cell_fill_color(cell), points)
        _draw_settlement_marker(surface, icon_assets, grid, cell, x, y)
        _draw_terrain_marker(surface, icon_assets, grid, cell, x, y, radius)
        _draw_topology(surface, icon_assets, grid, cell, x, y, radius)

    for cell in grid.get_all_cells():
        x, y = grid.axial_to_pixel(cell.q, cell.r)
        points = _hex_points(cache, x, y, radius)
        pygame.draw.polygon(surface, COLOR_BACKGROUND, points, line_width)

        if game.selected_source == (cell.q, cell.r):
            selected = _scaled_hex_points(cache, x, y, radius, UI_SELECTION_HIGHLIGHT_SCALE)
            pygame.draw.polygon(surface, COLOR_SELECTED, selected, selected_line_width)

        troops = cell.total_troops()
        if troops > 0 and not _is_hidden_from_you(cell):
            txt = font_units.render(str(troops), True, _owner_accent_color(cell.owner))
            text_x, text_y = _troop_text_center(grid, cell, x, y, radius)
            surface.blit(txt, txt.get_rect(center=(text_x, text_y)))

    _draw_rivers(surface, grid, line_width)
    draw_bottom_bar(surface, font_bar, grid, game)


def draw_bottom_bar(surface, font, grid, game):
    bar_height = grid.bottom_bar_height
    pygame.draw.rect(
        surface, COLOR_BOTTOM_BAR, (0, SCREEN_HEIGHT - bar_height, SCREEN_WIDTH, bar_height)
    )

    player_text = "You" if game.active_player == OWNER_PLAYER else "CPU"
    player_area, cpu_area = grid.count_control()
    status_segments = _status_segments(game, player_text, player_area, cpu_area, "   /   ")
    for separator in ("  /  ", " / ", "/"):
        if _segments_width(font, status_segments) <= SCREEN_WIDTH - 16:
            break
        status_segments = _status_segments(game, player_text, player_area, cpu_area, separator)
    _draw_centered_status(surface, font, status_segments, SCREEN_HEIGHT - bar_height // 2)


def get_cell_under_pixel(grid, px, py):
    cache = {}
    radius = grid.hex_radius
    for cell in grid.get_all_cells():
        x, y = grid.axial_to_pixel(cell.q, cell.r)
        points = _hex_points(cache, x, y, radius)
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


def _draw_centered_status(surface, font, segments, center_y):
    rendered = [font.render(text, True, color) for text, color in segments]
    total_width = sum(chunk.get_width() for chunk in rendered)
    x = (SCREEN_WIDTH - total_width) // 2
    for chunk in rendered:
        rect = chunk.get_rect(midleft=(x, center_y))
        surface.blit(chunk, rect)
        x = rect.right


def _status_segments(game, player_text, player_area, cpu_area, separator):
    return [
        (f"L: {game.level}", COLOR_SCORE),
        (separator, COLOR_SCORE),
        (f"T: {game.turn}", COLOR_SCORE),
        (separator, COLOR_SCORE),
        (player_text, COLOR_SCORE),
        (separator, COLOR_SCORE),
        (_phase_status_text(game), COLOR_SCORE),
        (separator, COLOR_SCORE),
        (f"{player_area}", COLOR_P1_DARK),
        ("/", COLOR_SCORE),
        (f"{cpu_area}", COLOR_P2_DARK),
    ]


def _segments_width(font, segments):
    return sum(font.size(text)[0] for text, _ in segments)


def _draw_rivers(surface, grid, grid_line_width):
    river_line_width = max(
        int(UI_MIN_LINE_WIDTH_PX),
        grid_line_width + int(UI_RIVER_LINE_WIDTH_DELTA_PX),
    )
    _draw_edge_segments(surface, grid, grid.river_edges, COLOR_RIVER, river_line_width)


def _draw_edge_segments(surface, grid, edges, color, line_width):
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
        pygame.draw.line(surface, color, p1, p2, line_width)


def _draw_terrain_marker(surface, icon_assets, grid, cell, x, y, radius):
    if grid.is_town_coord(cell.q, cell.r):
        return
    icon = icon_assets["terrain"].get(cell.terrain)
    if icon is None:
        return

    marker_y = y + radius * UI_TERRAIN_MARKER_Y_OFFSET_SCALE
    rect = icon.get_rect(center=(int(round(x)), int(round(marker_y))))
    surface.blit(icon, rect)


def _draw_settlement_marker(surface, icon_assets, grid, cell, x, y):
    if not grid.is_town_coord(cell.q, cell.r):
        return
    if grid.is_capital_coord(cell.q, cell.r):
        icon = icon_assets["capital"].get(cell.owner)
    else:
        icon = icon_assets["town"].get(cell.owner)
    if icon is None:
        return
    rect = icon.get_rect(center=(int(round(x)), int(round(y))))
    surface.blit(icon, rect)


def _draw_topology(surface, icon_assets, grid, cell, x, y, radius):
    if grid.frontline_topology(cell.q, cell.r) == "exposed":
        _draw_exposed_icon(surface, icon_assets.get("danger"), x, y, radius)


def _draw_exposed_icon(surface, icon, x, y, radius):
    if icon is None:
        return
    icon_y = y - radius * UI_EXPOSED_ICON_Y_OFFSET_SCALE
    rect = icon.get_rect(center=(int(round(x)), int(round(icon_y))))
    surface.blit(icon, rect)


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


def _hex_points(cache, x, y, radius):
    key = (x, y, radius)
    if key in cache:
        return cache[key]
    pts = [
        (x + radius * cos(pi / 180 * (60 * i)), y + radius * sin(pi / 180 * (60 * i)))
        for i in range(6)
    ]
    cache[key] = pts
    return pts


def _scaled_hex_points(cache, x, y, radius, scale):
    base_points = _hex_points(cache, x, y, radius)
    return [(x + (px - x) * scale, y + (py - y) * scale) for px, py in base_points]


def _grid_line_width():
    return max(int(UI_MIN_LINE_WIDTH_PX), int(UI_GRID_LINE_WIDTH_PX))


def _cell_fill_color(cell):
    if cell.owner == OWNER_PLAYER:
        return COLOR_P1_DARK
    if cell.owner == OWNER_CPU:
        return COLOR_P2_DARK
    return COLOR_NEUTRAL_DARK


def _owner_accent_color(owner):
    if owner == OWNER_PLAYER:
        return COLOR_P1_LIGHT
    if owner == OWNER_CPU:
        return COLOR_P2_LIGHT
    return COLOR_NEUTRAL_LIGHT


def _is_hidden_from_you(cell):
    return cell.owner == OWNER_CPU and cell.terrain == TERRAIN_FOREST


def _troop_text_center(grid, cell, x, y, radius):
    if grid.is_town_coord(cell.q, cell.r):
        return x, y + radius * UI_SETTLEMENT_TROOP_Y_OFFSET_SCALE
    return x, y


def _scaled_icon_size(radius, scale):
    return max(12, int(round(radius * scale)))


def _load_icon(path, size):
    key = (path, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    icon = pygame.image.load(path).convert_alpha()
    if icon.get_size() != (size, size):
        icon = pygame.transform.smoothscale(icon, (size, size))
    _ICON_CACHE[key] = icon
    return icon


def _load_tinted_icon(path, size, color, alpha):
    key = (path, size, color, alpha)
    if key in _TINTED_ICON_CACHE:
        return _TINTED_ICON_CACHE[key]

    base = _load_icon(path, size)
    tinted = base.copy()
    tint_layer = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
    tint_layer.fill((color[0], color[1], color[2], 255))
    tinted.blit(tint_layer, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    tinted.set_alpha(int(alpha))
    _TINTED_ICON_CACHE[key] = tinted
    return tinted
