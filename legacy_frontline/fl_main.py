# main.py

import pygame
from constants import *
from grid import Grid
from combat import FrontlineGameLogic
from ui import FrontlineUI

# Main function to start the game
def main():
    # Initialize game logic
    game_logic = FrontlineGameLogic()

    # Initialize UI
    ui = FrontlineUI(game_logic)

    # Set up the screen
    screen = ui.screen

    running = True
    clock = pygame.time.Clock()

    while running:
        # Handle events only if not in end-turn screen
        if not game_logic.in_end_turn: #TODO: Game still registers units during the end
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    # Handle arrow keys for navigation
                    if event.key == pygame.K_LEFT:
                        if ui.selected_x > 0:
                            ui.selected_x -= 1
                            # Prevent selecting frontline cell
                            if game_logic.grid.cells[ui.selected_y][ui.selected_x].frontline:
                                if ui.selected_x > game_logic.grid.frontline[ui.selected_y]:
                                    ui.selected_x -= 1
                                elif ui.selected_x < game_logic.grid.frontline[ui.selected_y]:
                                    ui.selected_x += 1
                    elif event.key == pygame.K_RIGHT:
                        if ui.selected_x < GRID_SIZE - 1:
                            ui.selected_x += 1
                            # Prevent selecting frontline cell
                            if game_logic.grid.cells[ui.selected_y][ui.selected_x].frontline:
                                if ui.selected_x > game_logic.grid.frontline[ui.selected_y]:
                                    ui.selected_x -= 1
                                elif ui.selected_x < game_logic.grid.frontline[ui.selected_y]:
                                    ui.selected_x += 1
                    elif event.key == pygame.K_UP:
                        if ui.selected_y > 0:
                            ui.selected_y -= 1
                            # Prevent selecting frontline cell
                            if game_logic.grid.cells[ui.selected_y][ui.selected_x].frontline:
                                if ui.selected_x > game_logic.grid.frontline[ui.selected_y]:
                                    ui.selected_x -= 1
                                elif ui.selected_x < game_logic.grid.frontline[ui.selected_y]:
                                    ui.selected_x += 1
                    elif event.key == pygame.K_DOWN:
                        if ui.selected_y < GRID_SIZE - 1:
                            ui.selected_y += 1
                            # Prevent selecting frontline cell
                            if game_logic.grid.cells[ui.selected_y][ui.selected_x].frontline:
                                if ui.selected_x > game_logic.grid.frontline[ui.selected_y]:
                                    ui.selected_x -= 1
                                elif ui.selected_x < game_logic.grid.frontline[ui.selected_y]:
                                    ui.selected_x += 1
                    # Handle unit placement keys: 1, 2, 3
                    elif event.key == pygame.K_1:
                        turn_over = game_logic.handle_input(ui.selected_x, ui.selected_y, '1')
                    elif event.key == pygame.K_2:
                        turn_over = game_logic.handle_input(ui.selected_x, ui.selected_y, '2')
                    elif event.key == pygame.K_3:
                        turn_over = game_logic.handle_input(ui.selected_x, ui.selected_y, '3')

            # If the turn is over, resolve combat and reset points
            if 'turn_over' in locals() and turn_over:
                game_logic.in_end_turn = True  # Set flag to indicate end-turn screen is active
                game_logic.resolve_combat()
                game_logic.reset_units_placement()
                ui.show_game_state()
                game_logic.in_end_turn = False  # Reset flag after end-turn screen
                del turn_over  # Remove the variable for the next loop

        else:
            # If in end-turn screen, process events to allow window to be responsive
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

        # Draw the game state
        ui.update()

        # Update the display
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()