# constants.py

# Screen and Grid Dimensions
GRID_SIZE = 9            # Grid size (15x15)
TILE_SIZE = 50            # Size of each grid tile
BB_HEIGHT = 50            # Bottom Bar height
BB_TK_MARGIN = 20         # Margin for the token bar
SCREEN_WIDTH = GRID_SIZE * TILE_SIZE
SCREEN_HEIGHT = GRID_SIZE * TILE_SIZE + BB_HEIGHT
FPS = 30                  # Frames per second

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_GREY = (50, 50, 50)
LIGHT_GREY = (200, 200, 200)
COLOR_1_TOKENS = (30, 100, 100)  # Dark Teal
COLOR_1_BACKGROUND = (150, 200, 200)  # Brighter Teal
COLOR_2_TOKENS = (125, 45, 45)   # Dark Red
COLOR_2_BACKGROUND = (200, 140, 140)   # Brighter Red

# Unit Costs
INFANTRY_COST = 1
ARTILLERY_COST = 2
AIR_COST = 3

# Combat Settings
MAX_THROWS_PER_COMBAT = 9
MAX_UNITS_PER_CELL = 9

# Mountain Generation Constants
MIN_MOUNTAINS = 20
MAX_MOUNTAINS = 40
MIN_MOUNTAIN_CLUSTERS = 3
MAX_MOUNTAIN_CLUSTERS = 6