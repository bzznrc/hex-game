### ui.py
import pygame
from math import pi, cos, sin
from constants import *


def draw(surface, font_tiles, font_bar, grid, game):
    surface.fill(COLOR_BACKGROUND)
    cache = {}

    for cell in grid.get_all_cells():
        x, y = grid.axial_to_pixel(cell.q, cell.r, HEX_RADIUS)
        points = _hex_points(cache, x, y, HEX_RADIUS)
        pygame.draw.polygon(surface, _cell_fill_color(cell), points)
        _draw_terrain(surface, cell, x, y)

    for cell in grid.get_all_cells():
        x, y = grid.axial_to_pixel(cell.q, cell.r, HEX_RADIUS)
        points = _hex_points(cache, x, y, HEX_RADIUS)
        pygame.draw.polygon(surface, COLOR_BACKGROUND, points, LINE_WIDTH)

        if game.selected_source == (cell.q, cell.r):
            selected = _scaled_hex_points(cache, x, y, HEX_RADIUS, HIGHLIGHT_SCALE)
            pygame.draw.polygon(surface, COLOR_SELECTED, selected, LINE_WIDTH + 1)

        p1 = cell.troops_of(OWNER_P1)
        p2 = cell.troops_of(OWNER_P2)
        if p1 > 0:
            txt = font_tiles.render(str(p1), True, COLOR_P1_LIGHT)
            surface.blit(txt, txt.get_rect(center=(x - 8, y)))
        if p2 > 0:
            txt = font_tiles.render(str(p2), True, COLOR_P2_LIGHT)
            surface.blit(txt, txt.get_rect(center=(x + 8, y)))

    draw_bottom_bar(surface, font_bar, grid, game)


def draw_bottom_bar(surface, font, grid, game):
    pygame.draw.rect(
        surface, (0, 0, 0), (0, SCREEN_HEIGHT - BB_HEIGHT, SCREEN_WIDTH, BB_HEIGHT)
    )

    player_text = "P1" if game.active_player == OWNER_P1 else "P2"
    p1_area, p2_area = grid.count_control()
    left = (
        f"T{game.turn} | Phase: {game.phase} | Player: {player_text} | "
        f"R:{game.reinforcements[game.active_player]} "
        f"M:{game.move_actions[game.active_player]} "
        f"PM:{game.post_move_actions[game.active_player]}"
    )
    right = f"Area P1:{p1_area} P2:{p2_area} | ENTER: end step | RMB: cancel"

    ls = font.render(left, True, COLOR_SCORE)
    rs = font.render(right, True, COLOR_SCORE)

    surface.blit(ls, (16, SCREEN_HEIGHT - BB_HEIGHT + 8))
    surface.blit(rs, (16, SCREEN_HEIGHT - BB_HEIGHT + 36))


def get_cell_under_pixel(grid, px, py):
    cache = {}
    for cell in grid.get_all_cells():
        x, y = grid.axial_to_pixel(cell.q, cell.r, HEX_RADIUS)
        points = _hex_points(cache, x, y, HEX_RADIUS)
        if _point_in_polygon((px, py), points):
            return cell
    return None


def _draw_terrain(surface, cell, x, y):
    if cell.terrain == TERRAIN_MOUNTAIN:
        pygame.draw.polygon(
            surface,
            COLOR_MOUNTAIN,
            [(x - 6, y + 4), (x, y - 8), (x + 6, y + 4)],
            1,
        )
    elif cell.terrain == TERRAIN_RIVER:
        pygame.draw.line(surface, COLOR_RIVER, (x - 6, y - 8), (x + 6, y + 8), 2)


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
    pts = [(x + radius * cos(pi / 180 * (60 * i)), y + radius * sin(pi / 180 * (60 * i))) for i in range(6)]
    cache[key] = pts
    return pts


def _scaled_hex_points(cache, x, y, radius, scale):
    base_points = _hex_points(cache, x, y, radius)
    return [(x + (px - x) * scale, y + (py - y) * scale) for px, py in base_points]


def _cell_fill_color(cell):
    if cell.frontline:
        return COLOR_FRONTLINE
    if cell.owner == OWNER_P1:
        return COLOR_P1_DARK
    if cell.owner == OWNER_P2:
        return COLOR_P2_DARK
    return COLOR_NEUTRAL_DARK
