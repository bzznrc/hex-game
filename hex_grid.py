### hex_grid.py
import math
from constants import *

class HexCell:
    def __init__(self, q, r, owner=OWNER_NEUTRAL, value=0):
        self.q = q
        self.r = r
        self.owner = owner
        self.selected = False
        self.value = value  # Additional score/value stored in the cell

    def set_owner(self, new_owner):
        self.owner = new_owner

    def get_owner(self):
        return self.owner

    def set_value(self, new_value):
        self.value = new_value

    def get_value(self):
        return self.value

class HexGrid:
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.cells = [[HexCell(q, r) for r in range(rows)] for q in range(cols)]

    @staticmethod
    def compute_grid_size():
        r = HEX_RADIUS
        available_width = SCREEN_WIDTH
        available_height = SCREEN_HEIGHT - BB_HEIGHT
        cols = max(1, int((available_width - 2*r) // (1.5*r) + 1))
        rows = max(1, int((available_height - r) // (math.sqrt(3)*r)))
        return cols, rows

    def axial_to_pixel(self, q, r, radius=HEX_RADIUS):
        x = radius * (1.5 * q + 1)
        if q % 2 == 0:
            y = radius + r * (math.sqrt(3)*radius)
        else:
            y = radius + (r + 0.5) * (math.sqrt(3)*radius)
        return (x, y)

    def select_cell(self, q, r):
        self.clear_selection()
        if 0 <= q < self.cols and 0 <= r < self.rows:
            self.cells[q][r].selected = True

    def clear_selection(self):
        for q in range(self.cols):
            for r in range(self.rows):
                self.cells[q][r].selected = False

    def set_cell_owner(self, q, r, owner):
        if 0 <= q < self.cols and 0 <= r < self.rows:
            cell = self.cells[q][r]
            if cell.owner == OWNER_NEUTRAL:
                cell.set_value(1)
            elif cell.owner == owner and cell.value < MAX_TILE_VALUE:
                cell.set_value(cell.value + 1)
            cell.set_owner(owner)

    def reset_cell(self, q, r):
        if 0 <= q < self.cols and 0 <= r < self.rows:
            cell = self.cells[q][r]
            cell.set_owner(OWNER_NEUTRAL)
            cell.set_value(0)

    def count_owners(self):
        p1 = p2 = neutral = 0
        for q in range(self.cols):
            for r in range(self.rows):
                owner = self.cells[q][r].get_owner()
                if owner == OWNER_P1:
                    p1 += 1
                elif owner == OWNER_P2:
                    p2 += 1
                else:
                    neutral += 1
        return p1, p2, neutral

    def get_all_cells(self):
        return [cell for row in self.cells for cell in row]