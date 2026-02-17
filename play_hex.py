import pygame

from config import (
    FONT_NAME_BAR,
    FONT_NAME_UNITS,
    FONT_PATH_REGULAR,
    FONT_PATH_UNITS,
    FONT_SIZE_BAR,
    FONT_SIZE_UNITS,
    FPS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WINDOW_TITLE,
)
from bgds.visual.assets import load_font
from hex_grid import HexGrid
from hex_game import HexGame
import ui

def play_hex():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    grid = HexGrid(*HexGrid.compute_grid_size())
    font_units = load_font(
        FONT_PATH_UNITS,
        FONT_SIZE_UNITS,
        fallback_family=FONT_NAME_UNITS,
    )
    font_bar = load_font(
        FONT_PATH_REGULAR,
        FONT_SIZE_BAR,
        fallback_family=FONT_NAME_BAR,
    )
    icon_assets = ui.load_icon_assets(grid.hex_radius)
    icon_radius = grid.hex_radius
    game = HexGame(grid)

    running = True
    while running:
        dt_seconds = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    game.end_player_step()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                cell = ui.get_cell_under_pixel(game.grid, mx, my)
                if cell:
                    game.handle_click(cell.q, cell.r, event.button)

        game.update(dt_seconds)
        if game.grid.hex_radius != icon_radius:
            icon_assets = ui.load_icon_assets(game.grid.hex_radius)
            icon_radius = game.grid.hex_radius
        ui.draw(screen, font_units, font_bar, icon_assets, game.grid, game)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    play_hex()
