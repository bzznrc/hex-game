import pygame
from constants import *
from hex_grid import HexGrid
import ui

def main():
    pygame.init()
    font_bar = pygame.font.SysFont(None, FONT_SIZE_BAR)
    font_tiles = pygame.font.SysFont(None, FONT_SIZE_TILES)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Hex Game")
    clock = pygame.time.Clock()

    cols, rows = HexGrid.compute_grid_size()
    total_cells = cols * rows
    grid = HexGrid(cols, rows)
    current_player = OWNER_P1

    running = True
    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    current_player = OWNER_P1 if current_player == OWNER_P2 else OWNER_P2
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                cell = ui.get_cell_under_pixel(grid, mx, my)
                if cell:
                    q, r = cell.q, cell.r
                    if event.button == 1:
                        grid.set_cell_owner(q, r, current_player)
                        grid.select_cell(q, r)
                    elif event.button == 3:
                        grid.reset_cell(q, r)

        screen.fill(COLOR_BACKGROUND)
        ui.draw_grid(screen, font_tiles, grid)
        p1_count, p2_count, neutral_count = grid.count_owners()
        ui.draw_bottom_bar(screen, font_bar, current_player, p1_count, p2_count, neutral_count, total_cells)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()