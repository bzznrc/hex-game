import pygame
from math import pi, cos, sin, hypot
from constants import *

def draw(surface, font_units, font_bar, font_terrain, font_terrain_tag, grid, game):
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
        _draw_terrain_marker(surface, font_terrain, cell, x, y, radius)
        _draw_topology(surface, grid, cell, x, y, radius)

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
            surface.blit(txt, txt.get_rect(center=(x, y)))
            _draw_terrain_status_tag(surface, font_terrain_tag, grid, cell, x, y, radius)

    _draw_rivers(surface, grid, line_width)
    draw_bottom_bar(surface, font_bar, grid, game)


def draw_bottom_bar(surface, font, grid, game):
    bar_height = grid.bottom_bar_height
    pygame.draw.rect(
        surface, COLOR_BOTTOM_BAR, (0, SCREEN_HEIGHT - bar_height, SCREEN_WIDTH, bar_height)
    )

    player_text = "You" if game.active_player == OWNER_PLAYER else "CPU"
    player_area, cpu_area = grid.count_control()
    if game.phase == PHASE_DEPLOYMENT:
        phase_info = (
            f"DEP {game.deploy_chunks_remaining}/{DEPLOY_CHUNKS_PER_TURN}"
            f" x{UNITS_PER_DEPLOY_CHUNK}"
        )
    elif game.phase == PHASE_ATTACK:
        phase_info = f"ATK {game.attacks_used}/{MAX_ATTACKS_PER_TURN}"
    else:
        phase_info = "MOV Units"

    parts = [
        f"Level {game.level}/{game.max_levels}",
        f"Turn {game.turn}",
        f"Player: {player_text}",
        f"Phase: {game.phase}",
        phase_info,
        f"Area You: {player_area}",
        f"Area CPU: {cpu_area}",
    ]
    status_line = UI_STATUS_SEPARATOR.join(parts)

    status_surface = font.render(status_line, True, COLOR_SCORE)
    status_rect = status_surface.get_rect(
        center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - bar_height // 2)
    )
    surface.blit(status_surface, status_rect)


def get_cell_under_pixel(grid, px, py):
    cache = {}
    radius = grid.hex_radius
    for cell in grid.get_all_cells():
        x, y = grid.axial_to_pixel(cell.q, cell.r)
        points = _hex_points(cache, x, y, radius)
        if _point_in_polygon((px, py), points):
            return cell
    return None


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


def _draw_terrain_marker(surface, font_terrain, cell, x, y, radius):
    marker = _terrain_marker_text(cell)
    if marker is None:
        return
    marker_y = y + radius * UI_TERRAIN_MARKER_Y_OFFSET_SCALE
    txt = font_terrain.render(marker, True, _owner_accent_color(cell.owner))
    surface.blit(txt, txt.get_rect(center=(x, marker_y)))


def _draw_terrain_status_tag(surface, font_terrain_tag, grid, cell, x, y, radius):
    tags = _status_tags(grid, cell)
    if not tags:
        return
    tag_x = x + radius * UI_TERRAIN_TAG_X_OFFSET_SCALE
    tag_y = y + radius * UI_TERRAIN_TAG_Y_OFFSET_SCALE
    txt = font_terrain_tag.render(" ".join(tags), True, _owner_accent_color(cell.owner))
    surface.blit(txt, txt.get_rect(midleft=(tag_x, tag_y)))


def _draw_topology(surface, grid, cell, x, y, radius):
    if grid.frontline_topology(cell.q, cell.r) == "exposed":
        _draw_exposed_dot(surface, x, y, radius, _owner_accent_color(cell.owner))


def _draw_exposed_dot(surface, x, y, radius, color):
    dot_y = y - radius * UI_EXPOSED_DOT_Y_OFFSET_SCALE
    dot_r = max(1, int(UI_EXPOSED_DOT_RADIUS_PX))
    pygame.draw.circle(surface, color, (int(round(x)), int(round(dot_y))), dot_r)


def _terrain_marker_text(cell):
    if cell.terrain == TERRAIN_MOUNTAIN:
        return UI_TERRAIN_MARK_MOUNTAIN
    if cell.terrain == TERRAIN_FOREST:
        return UI_TERRAIN_MARK_FOREST
    return None


def _terrain_status_tag_text(cell):
    if cell.terrain == TERRAIN_MOUNTAIN:
        return UI_TERRAIN_TAG_MOUNTAIN
    if cell.terrain == TERRAIN_FOREST:
        return UI_TERRAIN_TAG_FOREST
    return None


def _status_tags(grid, cell):
    tags = []
    terrain_tag = _terrain_status_tag_text(cell)
    if terrain_tag is not None:
        tags.append(terrain_tag)

    topology = grid.frontline_topology(cell.q, cell.r)
    if topology == "exposed" and cell.terrain != TERRAIN_MOUNTAIN:
        tags.append(UI_TERRAIN_TAG_EXPOSED)
    return tags


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
