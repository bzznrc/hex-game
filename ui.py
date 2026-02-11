import pygame
from math import pi, cos, sin, hypot
from constants import *

HIGHLIGHT_SCALE = 0.9


def draw(surface, font_units, font_bar, grid, game):
    surface.fill(COLOR_BACKGROUND)
    cache = {}
    radius = grid.hex_radius
    line_width = max(1, int(round(radius * 0.14)))
    selected_line_width = line_width + 1

    for cell in grid.get_all_cells():
        x, y = grid.axial_to_pixel(cell.q, cell.r)
        points = _hex_points(cache, x, y, radius)
        pygame.draw.polygon(surface, _cell_fill_color(cell), points)
        _draw_terrain(surface, cell, x, y, radius)

    for cell in grid.get_all_cells():
        x, y = grid.axial_to_pixel(cell.q, cell.r)
        points = _hex_points(cache, x, y, radius)
        pygame.draw.polygon(surface, COLOR_BACKGROUND, points, line_width)

        if game.selected_source == (cell.q, cell.r):
            selected = _scaled_hex_points(cache, x, y, radius, HIGHLIGHT_SCALE)
            pygame.draw.polygon(surface, COLOR_SELECTED, selected, selected_line_width)

        troops = cell.total_troops()
        if troops > 0:
            txt = font_units.render(str(troops), True, _owner_accent_color(cell.owner))
            text_y = y
            if cell.terrain in (TERRAIN_MOUNTAIN, TERRAIN_RIVER):
                text_y -= TERRAIN_TEXT_Y_OFFSET
            surface.blit(txt, txt.get_rect(center=(x, text_y)))

    _draw_boundaries(surface, grid)
    draw_bottom_bar(surface, font_bar, grid, game)


def draw_bottom_bar(surface, font, grid, game):
    bar_height = grid.bottom_bar_height
    pygame.draw.rect(
        surface, (0, 0, 0), (0, SCREEN_HEIGHT - bar_height, SCREEN_WIDTH, bar_height)
    )

    player_text = "P1" if game.active_player == OWNER_P1 else "P2"
    p1_area, p2_area = grid.count_control()
    if game.phase == PHASE_DEPLOYMENT:
        phase_info = f"DEP {game.reinforcements_remaining}/{REINFORCEMENTS_PER_PLAYER}"
    elif game.phase == PHASE_ATTACK:
        phase_info = f"ATK {game.attacks_used}/{MAX_ATTACKS_PER_TURN}"
    else:
        phase_info = "MOV Units"

    parts = [
        f"Turn {game.turn}",
        f"Player: {player_text}",
        f"Phase: {game.phase}",
        phase_info,
        f"Area P1: {p1_area}",
        f"Area P2: {p2_area}",
    ]
    status_line = "     |     ".join(parts)

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


def _draw_boundaries(surface, grid):
    radius = grid.hex_radius
    half_edge = radius * 0.52
    boundary_width = max(2, int(round(radius * 0.14)))
    for edge in grid.boundary_edges:
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
        pygame.draw.line(surface, COLOR_FRONTLINE, p1, p2, boundary_width)


def _draw_terrain(surface, cell, x, y, radius):
    accent = _owner_accent_color(cell.owner)
    terrain_stroke = max(2, int(round(radius * 0.09)))
    wave_amp = max(1.5, radius * 0.08)

    if cell.terrain == TERRAIN_MOUNTAIN:
        mountain_y = y + radius * 0.34
        mountain_len = radius * 1.05
        start_x = x - mountain_len / 2
        # Stylized "M" mountain profile with the same max height as the river wave.
        peaks = [-1.0, 1.0, -0.55, 1.0, -1.0]
        points = []
        last = len(peaks) - 1
        for i, factor in enumerate(peaks):
            t = i / last
            px = start_x + mountain_len * t
            py = mountain_y - wave_amp * factor
            points.append((int(round(px)), int(round(py))))
        pygame.draw.lines(surface, accent, False, points, terrain_stroke)
    elif cell.terrain == TERRAIN_RIVER:
        river_y = y + radius * 0.34
        river_len = radius * 0.95
        samples = 14
        points = []
        start_x = x - river_len / 2
        for i in range(samples + 1):
            t = i / samples
            px = start_x + river_len * t
            py = river_y + wave_amp * sin(2 * pi * t)
            points.append((int(round(px)), int(round(py))))
        pygame.draw.lines(surface, accent, False, points, terrain_stroke)


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


def _cell_fill_color(cell):
    if cell.owner == OWNER_P1:
        return COLOR_P1_DARK
    if cell.owner == OWNER_P2:
        return COLOR_P2_DARK
    return COLOR_NEUTRAL_DARK


def _owner_accent_color(owner):
    if owner == OWNER_P1:
        return COLOR_P1_LIGHT
    if owner == OWNER_P2:
        return COLOR_P2_LIGHT
    return COLOR_NEUTRAL_LIGHT
