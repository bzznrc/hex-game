### ui.py
import pygame
from math import pi, cos, sin
from constants import *

def draw_bottom_bar(surface, font, current_player, p1_count, p2_count, neutral_count, total_cells):
    pygame.draw.rect(surface, (0,0,0), (0, SCREEN_HEIGHT - BB_HEIGHT, SCREEN_WIDTH, BB_HEIGHT))

    player_str = "P1" if current_player == OWNER_P1 else "P2"
    left_text = f"Player: {player_str}"
    left_surf = font.render(left_text, True, COLOR_SCORE)
    surface.blit(left_surf, (20, SCREEN_HEIGHT - BB_HEIGHT + (BB_HEIGHT - left_surf.get_height())//2))

    right_text = f"P1: {p1_count} | P2: {p2_count} | Neutral: {neutral_count} | Total: {total_cells}"
    right_surf = font.render(right_text, True, COLOR_SCORE)
    right_x = SCREEN_WIDTH - 20 - right_surf.get_width()
    surface.blit(right_surf, (right_x, SCREEN_HEIGHT - BB_HEIGHT + (BB_HEIGHT - right_surf.get_height())//2))

def draw_grid(surface, font, hex_grid):
    cells = hex_grid.get_all_cells()
    hex_points_cache = {}

    for cell in cells:
        q, r = cell.q, cell.r
        x, y = hex_grid.axial_to_pixel(q, r, HEX_RADIUS)
        points = _hex_points(hex_points_cache, x, y, HEX_RADIUS)

        fill_color = _cell_fill_color(cell)
        pygame.draw.polygon(surface, fill_color, points)

    for cell in cells:
        q, r = cell.q, cell.r
        x, y = hex_grid.axial_to_pixel(q, r, HEX_RADIUS)
        base_points = _hex_points(hex_points_cache, x, y, HEX_RADIUS)
        pygame.draw.polygon(surface, COLOR_BACKGROUND, base_points, LINE_WIDTH)

        if cell.selected:
            highlight_color = _highlight_color_for_cell(cell)
            highlight_points = _scaled_hex_points(hex_points_cache, x, y, HEX_RADIUS, HIGHLIGHT_SCALE)
            pygame.draw.polygon(surface, highlight_color, highlight_points, LINE_WIDTH)

        if cell.owner != OWNER_NEUTRAL:
            value_text = str(cell.value)
            text_color = COLOR_P1_LIGHT if cell.owner == OWNER_P1 else COLOR_P2_LIGHT
            value_surf = font.render(value_text, True, text_color)
            value_rect = value_surf.get_rect(center=(x, y))
            surface.blit(value_surf, value_rect)

def get_cell_under_pixel(hex_grid, px, py):
    # Perform polygon hit testing to find cell at (px, py).
    # We'll replicate what we did before: loop through all cells and test polygons.
    # This ensures main remains light and just calls this function.
    hex_points_cache = {}
    for cell in hex_grid.get_all_cells():
        q, r = cell.q, cell.r
        x, y = hex_grid.axial_to_pixel(q, r, HEX_RADIUS)
        points = _hex_points(hex_points_cache, x, y, HEX_RADIUS)
        if _point_in_polygon((px, py), points):
            return cell
    return None

def _point_in_polygon(point, polygon):
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i+1)%n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1)*(y - y1)/(y2 - y1)+x1):
            inside = not inside
    return inside

def _hex_points(cache, x, y, radius):
    key = (x, y, radius)
    if key in cache:
        return cache[key]
    pts = [(x + radius*cos(pi/180*(60*i)), y + radius*sin(pi/180*(60*i))) for i in range(6)]
    cache[key] = pts
    return pts

def _scaled_hex_points(cache, x, y, radius, scale):
    base_points = _hex_points(cache, x, y, radius)
    return [(x + (px-x)*scale, y + (py-y)*scale) for px, py in base_points]

def _cell_fill_color(cell):
    if cell.owner == OWNER_P1:
        return COLOR_P1_DARK
    elif cell.owner == OWNER_P2:
        return COLOR_P2_DARK
    return COLOR_NEUTRAL_DARK

def _highlight_color_for_cell(cell):
    if cell.owner == OWNER_P1:
        return COLOR_P1_LIGHT
    elif cell.owner == OWNER_P2:
        return COLOR_P2_LIGHT
    return COLOR_NEUTRAL_LIGHT