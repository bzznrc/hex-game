import pygame
from math import pi, cos, sin, hypot

from config import (
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
from bgds.visual.assets import load_icon_surface, load_tinted_icon_surface
from bgds.visual.colors import (
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
from bgds.visual.statusbar import draw_centered_status_bar

def load_icon_assets(hex_radius):
    terrain_size = _scaled_icon_size(hex_radius, UI_TERRAIN_ICON_SIZE_SCALE)
    danger_size = _scaled_icon_size(hex_radius, UI_EXPOSED_ICON_SIZE_SCALE)
    capital_size = _scaled_icon_size(hex_radius, UI_CAPITAL_ICON_SIZE_SCALE)
    town_size = _scaled_icon_size(hex_radius, UI_TOWN_ICON_SIZE_SCALE)
    return {
        "terrain": {
            TERRAIN_FOREST: load_icon_surface(ICON_PATH_FOREST, terrain_size),
            TERRAIN_MOUNTAIN: load_icon_surface(ICON_PATH_MOUNTAIN, terrain_size),
        },
        "danger": load_icon_surface(ICON_PATH_DANGER, danger_size),
        "capital": {
            OWNER_PLAYER: load_tinted_icon_surface(
                ICON_PATH_CAPITAL,
                capital_size,
                COLOR_AQUA,
                UI_CAPITAL_ICON_ALPHA,
            ),
            OWNER_CPU: load_tinted_icon_surface(
                ICON_PATH_CAPITAL,
                capital_size,
                COLOR_CORAL,
                UI_CAPITAL_ICON_ALPHA,
            ),
        },
        "town": {
            OWNER_PLAYER: load_tinted_icon_surface(
                ICON_PATH_TOWN,
                town_size,
                COLOR_AQUA,
                UI_TOWN_ICON_ALPHA,
            ),
            OWNER_CPU: load_tinted_icon_surface(
                ICON_PATH_TOWN,
                town_size,
                COLOR_CORAL,
                UI_TOWN_ICON_ALPHA,
            ),
        },
    }

def draw(surface, font_units, font_bar, icon_assets, grid, game):
    surface.fill(COLOR_CHARCOAL)
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
        pygame.draw.polygon(surface, COLOR_CHARCOAL, points, line_width)

        if game.selected_source == (cell.q, cell.r):
            selected = _scaled_hex_points(cache, x, y, radius, UI_SELECTION_HIGHLIGHT_SCALE)
            pygame.draw.polygon(surface, COLOR_AMBER, selected, selected_line_width)

        troops = cell.total_troops()
        if troops > 0 and not _is_hidden_from_you(cell):
            txt = font_units.render(str(troops), True, _owner_accent_color(cell.owner))
            text_x, text_y = _troop_text_center(grid, cell, x, y, radius)
            surface.blit(txt, txt.get_rect(center=(text_x, text_y)))

    _draw_rivers(surface, grid, line_width)
    draw_bottom_bar(surface, font_bar, grid, game)

def draw_bottom_bar(surface, font, grid, game):
    player_text = "You" if game.active_player == OWNER_PLAYER else "CPU"
    player_area, cpu_area = grid.count_control()
    draw_centered_status_bar(
        surface=surface,
        font=font,
        screen_width_px=SCREEN_WIDTH,
        screen_height_px=SCREEN_HEIGHT,
        bar_height_px=grid.bottom_bar_height,
        items=[
            f"L: {game.level}",
            f"T: {game.turn}",
            player_text,
            _phase_status_text(game),
            (f"{player_area}", COLOR_DEEP_TEAL),
            (f"{cpu_area}", COLOR_BRICK_RED),
        ],
        background_color=COLOR_NEAR_BLACK,
        default_text_color=COLOR_SOFT_WHITE,
        separator=UI_STATUS_SEPARATOR,
        separator_color=COLOR_SOFT_WHITE,
    )

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

def _draw_rivers(surface, grid, grid_line_width):
    river_line_width = max(
        int(UI_MIN_LINE_WIDTH_PX),
        grid_line_width + int(UI_RIVER_LINE_WIDTH_DELTA_PX),
    )
    _draw_edge_segments(surface, grid, grid.river_edges, COLOR_STEEL_BLUE, river_line_width)

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

