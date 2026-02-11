import pygame
from constants import *
from hex_grid import HexGrid
from frontline_game import FrontlineGame
import ui


def main():
    pygame.init()
    font_bar = pygame.font.SysFont(None, FONT_SIZE_BAR)
    font_tiles = pygame.font.SysFont(None, FONT_SIZE_TILES)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Hex Frontline")
    clock = pygame.time.Clock()

    grid = HexGrid(*HexGrid.compute_grid_size())
    game = FrontlineGame(grid)

    running = True
    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    game.end_player_step()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                cell = ui.get_cell_under_pixel(grid, mx, my)
                if cell:
                    game.handle_click(cell.q, cell.r, event.button)

        ui.draw(screen, font_tiles, font_bar, grid, game)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
