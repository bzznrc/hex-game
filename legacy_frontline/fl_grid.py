# grid.py
import random
from constants import *
from enum import Enum

class UnitType(Enum):
    INFANTRY = 1
    ARTILLERY = 2
    AIR = 3

class TerrainType(Enum):
    PLAIN = 1
    MOUNTAIN = 2
    RIVER = 3

class Unit:
    def __init__(self, unit_type: UnitType, player: int):
        self.unit_type = unit_type
        self.player = player
        self.p_health, self.p_attack, self.range_, self.point_cost = self.get_unit_stats()
        self.x = None  # To be set when placed in a cell
        self.y = None  # To be set when placed in a cell

    def get_unit_stats(self):
        """Return the stats based on the unit type."""
        if self.unit_type == UnitType.INFANTRY:
            return 1, 2, 1, INFANTRY_COST  # Infantry has 1 HP for testing
        elif self.unit_type == UnitType.ARTILLERY:
            return 2, 3, 2, ARTILLERY_COST
        elif self.unit_type == UnitType.AIR:
            return 1, 2, 3, AIR_COST

    def attack(self, target_unit):
        """Perform an attack on the target unit."""
        damage = min(target_unit.p_health, random.randint(1, self.p_attack))
        target_unit.take_damage(damage)
        return damage

    def take_damage(self, amount):
        """Reduce the health of the unit."""
        self.p_health = max(0, self.p_health - amount)

class Cell:
    def __init__(self, y, x):
        # Using a dictionary to store units by type for easier management
        self.units = {UnitType.INFANTRY: [], UnitType.ARTILLERY: [], UnitType.AIR: []}
        self.player = 0
        self.has_bridge = False  # For future implementation
        self.terrain_type = TerrainType.PLAIN  # Default terrain
        self.frontline = False  # Indicates if this cell is part of the frontline
        self.y = y  # Row index
        self.x = x  # Column index

    def add_unit(self, unit: Unit):
        """Add a unit to the cell and update the player ownership."""
        if self.frontline:
            raise ValueError("Cannot place units on the frontline.")
        if self.player == 0:
            self.player = unit.player
        if unit.player == self.player:
            self.units[unit.unit_type].append(unit)
            unit.x = self.x
            unit.y = self.y
        else:
            raise ValueError("Cannot add a unit from a different player to this cell.")

    def remove_unit(self, unit: Unit):
        """Remove a unit from the cell and update the player ownership."""
        self.units[unit.unit_type].remove(unit)
        # Capture coordinates before nullifying
        unit_x = unit.x
        unit_y = unit.y
        unit.x = None
        unit.y = None
        if not any(self.units.values()):
            self.player = 0  # If no units left, cell becomes neutral
        return unit_x, unit_y

    def get_total_units(self):
        """Return the total number of units in the cell."""
        return sum(len(units) for units in self.units.values())

class Grid:
    def __init__(self):
        self.cells = [[Cell(y, x) for x in range(GRID_SIZE)] for y in range(GRID_SIZE)]
        self.frontline = self.create_frontline()
        self.assign_initial_ownership()
        self.generate_mountains()
        self.generate_river()

    def create_frontline(self):
        """Generate a frontline in the middle column."""
        frontline_column = GRID_SIZE // 2
        for y in range(GRID_SIZE):
            self.cells[y][frontline_column].frontline = True
            self.cells[y][frontline_column].player = 0  # Ensure frontline is neutral
        return [frontline_column for _ in range(GRID_SIZE)]  # Frontline is a vertical line in the middle

    def assign_initial_ownership(self):
        """Assign ownership to cells left of frontline to P1 and right to P2."""
        for y in range(GRID_SIZE):
            frontline_x = self.frontline[y]
            for x in range(GRID_SIZE):
                if x < frontline_x and not self.cells[y][x].frontline:
                    self.cells[y][x].player = 1
                elif x > frontline_x and not self.cells[y][x].frontline:
                    self.cells[y][x].player = 2
                # Frontline remains neutral (player=0)

    def place_unit(self, x, y, unit: Unit):
        """Place a unit in the specified cell."""
        cell = self.cells[y][x]
        if cell.frontline:
            return False  # Cannot place units on the frontline
        if unit.player == 1 and x > self.frontline[y]:
            return False  # Player 1 cannot place units on the right side of the frontline
        if unit.player == 2 and x < self.frontline[y]:
            return False  # Player 2 cannot place units on the left side of the frontline

        if cell.player == 0 or cell.player == unit.player:
            # Check if adding the unit exceeds MAX_UNITS_PER_CELL
            total_units = cell.get_total_units()
            if total_units + 1 <= MAX_UNITS_PER_CELL:
                cell.add_unit(unit)
                return True

        return False

    def advance_frontline(self, y, direction: int):
        """
        Advances the frontline in the specified row (y) by the given direction.
        The winning side's entire line moves forward by one cell.
        Cell ownership is updated accordingly.

        Args:
            y (int): The row index where the frontline is advancing.
            direction (int): 1 for Player 1 advancing (right), -1 for Player 2 advancing (left).
        """

        current_frontline_x = self.frontline[y]
        new_frontline_x = current_frontline_x + direction

        if 0 <= new_frontline_x < GRID_SIZE:
            # Update frontline cells
            self.cells[y][current_frontline_x].frontline = False
            self.cells[y][new_frontline_x].frontline = True
            self.frontline[y] = new_frontline_x
            print(f"Frontline advanced to x={new_frontline_x} in row={y}")

            # Shift units based on direction
            if direction == 1:  # Player 1 advances to the right
                # Shift Player 1 units forward by one cell
                for x in range(current_frontline_x -1, -1, -1):
                    source_cell = self.cells[y][x]
                    if source_cell.player == 1 and source_cell.get_total_units() > 0:
                        target_x = x + 1
                        target_cell = self.cells[y][target_x]
                        # Transfer all units
                        for unit_type, units in source_cell.units.items():
                            target_cell.units[unit_type].extend(units)
                            for unit in units:
                                unit.x = target_x
                                unit.y = y
                        # Clear source cell
                        source_cell.units = {ut: [] for ut in UnitType}
                        print(f"P1 moved units from ({x}, {y}) to ({target_x}, {y})")

            elif direction == -1:  # Player 2 advances to the left
                # Shift Player 2 units forward by one cell
                for x in range(current_frontline_x +1, GRID_SIZE):
                    source_cell = self.cells[y][x]
                    if source_cell.player == 2 and source_cell.get_total_units() > 0:
                        target_x = x -1
                        target_cell = self.cells[y][target_x]
                        # Transfer all units
                        for unit_type, units in source_cell.units.items():
                            target_cell.units[unit_type].extend(units)
                            for unit in units:
                                unit.x = target_x
                                unit.y = y
                        # Clear source cell
                        source_cell.units = {ut: [] for ut in UnitType}
                        print(f"P2 moved units from ({x}, {y}) to ({target_x}, {y})")

            # Reassign ownership for all cells in the row based on new frontline position
            for x in range(GRID_SIZE):
                cell = self.cells[y][x]
                if cell.frontline:
                    cell.player = 0  # Frontline remains neutral
                elif x < new_frontline_x:
                    cell.player = 1
                elif x > new_frontline_x:
                    cell.player = 2

            # Enhanced Debug: Print the state after ownership reassignment
            print(f"DEBUG: After Ownership Reassignment - Row {y}, Frontline at x={new_frontline_x}")
            for x in range(GRID_SIZE):
                cell = self.cells[y][x]
                unit_counts = {ut.name[:3]: len(units) for ut, units in cell.units.items() if units}
                unit_summary = ', '.join([f"{count} {ut}" for ut, count in unit_counts.items()]) if unit_counts else "0"
                print(f"  Cell ({x}, {y}): P{cell.player} [{unit_summary}]")
        else:
            print(f"Cannot advance frontline beyond grid bounds for row {y}. Current Frontline: {current_frontline_x}, Direction: {direction}")

    def generate_mountains(self):
        """Randomly generate mountain clusters on the grid."""
        min_mountains = MIN_MOUNTAINS
        max_mountains = MAX_MOUNTAINS
        min_clusters = MIN_MOUNTAIN_CLUSTERS
        max_clusters = MAX_MOUNTAIN_CLUSTERS

        num_clusters = random.randint(min_clusters, max_clusters)
        total_mountains = random.randint(min_mountains, max_mountains)

        for _ in range(num_clusters):
            cluster_size = max(1, total_mountains // num_clusters)
            start_x = random.randint(0, GRID_SIZE -1)
            start_y = random.randint(0, GRID_SIZE -1)

            for _ in range(cluster_size):
                if start_x < 0 or start_x >= GRID_SIZE or start_y < 0 or start_y >= GRID_SIZE:
                    continue
                cell = self.cells[start_y][start_x]
                if cell.terrain_type == TerrainType.PLAIN and not cell.frontline:
                    cell.terrain_type = TerrainType.MOUNTAIN
                    total_mountains -=1
                    if total_mountains <=0:
                        break
                # Expand cluster randomly
                direction = random.choice(['up', 'down', 'left', 'right'])
                if direction == 'up':
                    start_y -=1
                elif direction == 'down':
                    start_y +=1
                elif direction == 'left':
                    start_x -=1
                elif direction == 'right':
                    start_x +=1

    def generate_river(self):
        """Generate a single river flowing from top to bottom."""
        # Start position near the frontline at the top row
        frontline_start_x = self.frontline[0]
        start_x_variation = random.choice([-1, 0, 1])
        start_x = frontline_start_x + start_x_variation
        start_x = max(0, min(GRID_SIZE -1, start_x))
        y = 0
        x = start_x

        while y < GRID_SIZE:
            cell = self.cells[y][x]
            if cell.terrain_type == TerrainType.PLAIN and not cell.frontline:
                cell.terrain_type = TerrainType.RIVER
            y +=1
            # Randomly decide horizontal movement: -1, 0, +1
            move = random.choice([-1, 0, 1])
            x += move
            x = max(0, min(GRID_SIZE -1, x))  # Keep within bounds
