# ui.py
import pygame
from constants import *
from grid import Grid, UnitType, TerrainType
from combat import FrontlineGameLogic
from enum import Enum

class FrontlineUI:
    def __init__(self, game_logic: FrontlineGameLogic):
        self.game_logic = game_logic
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Frontline")
        self.font = pygame.font.SysFont(None, 24)
        self.clock = pygame.time.Clock()
        self.selected_x = GRID_SIZE // 2  # Initialize selected cell to center
        self.selected_y = GRID_SIZE // 2

    def draw_selection_outline(self):
        """Draws a white outline around the selected cell."""
        rect = pygame.Rect(
            self.selected_x * TILE_SIZE,
            self.selected_y * TILE_SIZE,
            TILE_SIZE,
            TILE_SIZE
        )
        pygame.draw.rect(self.screen, WHITE, rect, 3)

    def draw_grid(self):
        """Draws the grid, terrains, frontline, and units on the screen."""
        self.screen.fill(WHITE)

        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                cell = self.game_logic.grid.cells[y][x]
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)

                # Determine cell color based on ownership
                if cell.player == 1:
                    cell_color = COLOR_1_BACKGROUND
                elif cell.player == 2:
                    cell_color = COLOR_2_BACKGROUND
                else:
                    cell_color = WHITE  # Neutral cells

                # Override cell color to DARK_GREY if it's a frontline cell
                if cell.frontline:
                    cell_color = DARK_GREY

                # Draw the cell background
                pygame.draw.rect(self.screen, cell_color, rect)

                # Draw terrain if present
                if cell.terrain_type == TerrainType.MOUNTAIN:
                    self.draw_mountain(rect)
                elif cell.terrain_type == TerrainType.RIVER:
                    self.draw_river(rect)

                # Draw grid lines
                pygame.draw.rect(self.screen, LIGHT_GREY, rect, 1)

                # Draw units if any
                if cell.get_total_units() > 0:
                    self.draw_units(cell, rect)

        # Draw the token bar
        self.draw_token_bar()

        # Draw selection outline
        self.draw_selection_outline()

    def draw_mountain(self, rect):
        """Draws diagonal stripes to represent mountains."""
        stripe_color = LIGHT_GREY
        stripe_width = 2
        spacing = 5
        for i in range(0, TILE_SIZE, spacing):  # Changed from -TILE_SIZE to 0
            pygame.draw.line(
                self.screen,
                stripe_color,
                (rect.x + i, rect.y),
                (rect.x + i + TILE_SIZE, rect.y + TILE_SIZE),
                stripe_width
            )

    def draw_river(self, rect):
        """Draws two vertical lines near the center to represent rivers."""
        stripe_color = LIGHT_GREY
        stripe_width = 4
        # Define positions for the two vertical lines
        line1_x = rect.x + TILE_SIZE // 3
        line2_x = rect.x + 2 * TILE_SIZE // 3
        pygame.draw.line(
            self.screen,
            stripe_color,
            (line1_x, rect.y),
            (line1_x, rect.y + TILE_SIZE),
            stripe_width
        )
        pygame.draw.line(
            self.screen,
            stripe_color,
            (line2_x, rect.y),
            (line2_x, rect.y + TILE_SIZE),
            stripe_width
        )

    def draw_units(self, cell, rect):
        """Draws units in a 3x3 grid within the cell, sorted as infantry, artillery, air."""
        # Sort units by type: Infantry, Artillery, Air
        sorted_units = []
        for unit_type in [UnitType.INFANTRY, UnitType.ARTILLERY, UnitType.AIR]:
            sorted_units.extend(cell.units[unit_type])

        # Limit to MAX_UNITS_PER_CELL
        sorted_units = sorted_units[:MAX_UNITS_PER_CELL]

        # Calculate positions for 3x3 grid
        unit_size = TILE_SIZE // 4  # Size of each unit icon
        padding = TILE_SIZE // 8
        positions = [
            (rect.x + padding + unit_size // 2, rect.y + padding + unit_size // 2),
            (rect.x + TILE_SIZE // 2, rect.y + padding + unit_size // 2),
            (rect.x + TILE_SIZE - padding - unit_size // 2, rect.y + padding + unit_size // 2),
            (rect.x + padding + unit_size // 2, rect.y + TILE_SIZE // 2),
            (rect.x + TILE_SIZE // 2, rect.y + TILE_SIZE // 2),
            (rect.x + TILE_SIZE - padding - unit_size // 2, rect.y + TILE_SIZE // 2),
            (rect.x + padding + unit_size // 2, rect.y + TILE_SIZE - padding - unit_size // 2),
            (rect.x + TILE_SIZE // 2, rect.y + TILE_SIZE - padding - unit_size // 2),
            (rect.x + TILE_SIZE - padding - unit_size // 2, rect.y + TILE_SIZE - padding - unit_size // 2),
        ]

        for idx, unit in enumerate(sorted_units):
            if idx >= 9:
                break  # Maximum of 9 units per cell
            pos = positions[idx]
            if unit.unit_type == UnitType.INFANTRY:
                self.draw_infantry(pos, unit.player, unit_size)
            elif unit.unit_type == UnitType.ARTILLERY:
                self.draw_artillery(pos, unit.player, unit_size)
            elif unit.unit_type == UnitType.AIR:
                self.draw_air(pos, unit.player, unit_size)

    def draw_infantry(self, position, player, size):
        """Draws an infantry unit as a circle."""
        color = COLOR_1_TOKENS if player == 1 else COLOR_2_TOKENS
        pygame.draw.circle(self.screen, color, position, size // 2)
        pygame.draw.circle(self.screen, BLACK, position, size // 2, 1)  # Border

    def draw_artillery(self, position, player, size):
        """Draws an artillery unit as a square."""
        color = COLOR_1_TOKENS if player == 1 else COLOR_2_TOKENS
        rect = pygame.Rect(position[0] - size // 2, position[1] - size // 2, size, size)
        pygame.draw.rect(self.screen, color, rect)
        pygame.draw.rect(self.screen, BLACK, rect, 1)  # Border

    def draw_air(self, position, player, size):
        """Draws an air unit as a triangle."""
        color = COLOR_1_TOKENS if player == 1 else COLOR_2_TOKENS
        point1 = (position[0], position[1] - size // 2)
        point2 = (position[0] - size // 2, position[1] + size // 2)
        point3 = (position[0] + size // 2, position[1] + size // 2)
        pygame.draw.polygon(self.screen, color, [point1, point2, point3])
        pygame.draw.polygon(self.screen, BLACK, [point1, point2, point3], 1)  # Border

    def draw_token_bar(self):
        """Draws a bar at the bottom of the screen showing the remaining points for each player."""
        # Define sections for Player 1 and Player 2
        p1_points = self.game_logic.player_points[1]
        p2_points = self.game_logic.player_points[2]

        # Calculate positions
        p1_start_x = BB_TK_MARGIN
        p1_y_pos = GRID_SIZE * TILE_SIZE + BB_HEIGHT // 2 - 10

        p2_start_x = SCREEN_WIDTH - BB_TK_MARGIN
        p2_y_pos = GRID_SIZE * TILE_SIZE + BB_HEIGHT // 2 - 10

        # Display Player 1 Points
        p1_text = self.font.render(f"P1 Points: {p1_points}", True, BLACK)
        self.screen.blit(p1_text, (p1_start_x, p1_y_pos))

        # Display Player 2 Points
        p2_text = self.font.render(f"P2 Points: {p2_points}", True, BLACK)
        p2_rect = p2_text.get_rect(topright=(p2_start_x, p2_y_pos))
        self.screen.blit(p2_text, p2_rect)

    def show_game_state(self):
        """Displays the current game state on the screen."""
        font_large = pygame.font.SysFont(None, 55)
        font_small = pygame.font.SysFont(None, 30)

        p1_area, p2_area = self.game_logic.calculate_areas()
        bg_color = COLOR_1_BACKGROUND if p1_area > p2_area else COLOR_2_BACKGROUND

        # Display the background for the message
        message_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        message_surface.fill(bg_color)
        self.screen.blit(message_surface, (0, 0))

        # Render "Turn Ends" message
        turn_message = font_large.render("Turn Ends", True, BLACK)
        turn_message_rect = turn_message.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 100))
        self.screen.blit(turn_message, turn_message_rect)

        # Display game statistics
        messages = [
            f"P1 Area: {p1_area} squares",
            f"P2 Area: {p2_area} squares",
        ]

        y_offset = SCREEN_HEIGHT // 2 + 20
        for message in messages:
            text = font_small.render(message, True, DARK_GREY)
            self.screen.blit(text, (20, y_offset))
            y_offset += 30

        pygame.display.flip()
        pygame.time.wait(3000)

    def update(self):
        """Update the UI by drawing grid and token bar."""
        self.draw_grid()