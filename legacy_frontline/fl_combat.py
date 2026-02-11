# game_logic.py
import random
from constants import *
from grid import *

class FrontlineGameLogic:
    def __init__(self):
        self.grid = Grid()
        self.turn_counter = 0
        # Initialize points for each player; adjust as needed
        self.player_points = {1: 10, 2: 10}  # Starting points for Player 1 and Player 2
        self.in_end_turn = False

    def handle_input(self, selected_x, selected_y, unit_key):
        """
        Handle user input for placing units on the grid via keyboard.

        Args:
            selected_x (int): The current selected x position on the grid.
            selected_y (int): The current selected y position on the grid.
            unit_key (str): The key pressed by the user ('1', '2', '3') to place units.
        """
        if unit_key not in ['1', '2', '3']:
            return False  # Invalid key

        unit_type = None
        if unit_key == '1':
            unit_type = UnitType.INFANTRY
        elif unit_key == '2':
            unit_type = UnitType.ARTILLERY
        elif unit_key == '3':
            unit_type = UnitType.AIR

        if unit_type:
            # Determine player based on side
            if selected_x < self.grid.frontline[selected_y]:
                player = 1
            elif selected_x > self.grid.frontline[selected_y]:
                player = 2
            else:
                # Cannot place units on frontline
                print(f"Cannot place units on frontline at ({selected_x}, {selected_y})")
                return False

            unit = Unit(unit_type, player)
            if self.player_points[player] >= unit.point_cost:
                if self.grid.place_unit(selected_x, selected_y, unit):
                    self.player_points[player] -= unit.point_cost
                    print(f"P{player} placed {unit_type.name} at ({selected_x}, {selected_y}). Remaining points: {self.player_points[player]}")
                    # Check if both players have exhausted their points
                    if self.player_points[1] <= 0 and self.player_points[2] <= 0:
                        return True  # Turn should end
                else:
                    print(f"Failed to place {unit_type.name} at ({selected_x}, {selected_y}).")
            else:
                print(f"P{player} does not have enough points to place {unit_type.name}.")
        return False

    def resolve_combat(self):
        """Resolve combat for all rows with opposing units."""
        for y in range(GRID_SIZE):
            frontline_x = self.grid.frontline[y]
            p1_units = self.get_units_in_range(player=1, y=y)
            p2_units = self.get_units_in_range(player=2, y=y)

            if p1_units and p2_units:
                # Log initial combat state
                p1_summary = self.get_unit_summary(p1_units)
                p2_summary = self.get_unit_summary(p2_units)
                print(f"P1 {p1_summary} v. P2 {p2_summary} in ({frontline_x}, {y})")

                # Determine bonuses
                p1_bonuses, p2_bonuses = self.determine_bonuses(p1_units, p2_units)
                if p1_bonuses:
                    bonus_str = ', '.join(p1_bonuses)
                    print(f"P1 Bonuses: {bonus_str}")
                if p2_bonuses:
                    bonus_str = ', '.join(p2_bonuses)
                    print(f"P2 Bonuses: {bonus_str}")

                # Calculate attack probabilities
                total_p1 = len(p1_units)
                total_p2 = len(p2_units)
                total = total_p1 + total_p2
                p1_attack_prob = total_p1 / total if total > 0 else 0
                p2_attack_prob = total_p2 / total if total > 0 else 0
                print(f"Attack Probabilities - P1: {p1_attack_prob:.2f}, P2: {p2_attack_prob:.2f}")

                # Perform throws
                self.perform_throws(y, p1_units, p2_units, p1_bonuses, p2_bonuses)

            elif p1_units and not p2_units:
                # Only Player 1 has units adjacent to frontline
                p1_summary = self.get_unit_summary(p1_units)
                print(f"P1 {p1_summary} in ({frontline_x}, {y}) automatically wins combat.")
                print(f"P1 wins combat at row {y}. Advancing frontline to the right.")
                self.grid.advance_frontline(y, direction=1)

            elif p2_units and not p1_units:
                # Only Player 2 has units adjacent to frontline
                p2_summary = self.get_unit_summary(p2_units)
                print(f"P2 {p2_summary} in ({frontline_x}, {y}) automatically wins combat.")
                print(f"P2 wins combat at row {y}. Advancing frontline to the left.")
                self.grid.advance_frontline(y, direction=-1)

    def get_units_in_range(self, player, y):
        """Get all units of a player in a specific row within their range."""
        frontline_x = self.grid.frontline[y]
        units = []
        for x in range(GRID_SIZE):
            cell = self.grid.cells[y][x]
            if cell.player == player and not cell.frontline:
                for unit_type, unit_list in cell.units.items():
                    for unit in unit_list:
                        distance = abs(x - frontline_x)
                        if distance <= unit.range_:
                            units.append(unit)
        return units

    def get_unit_summary(self, units):
        """Generate a summary string for a list of units."""
        summary = {}
        for unit in units:
            key = unit.unit_type.name[:3]
            summary[key] = summary.get(key, 0) + 1
        summary_str = '[' + ', '.join([f"{count} {ut}" for ut, count in summary.items()]) + ']'
        return summary_str

    def determine_bonuses(self, p1_units, p2_units):
        """
        Determine bonuses for each player based on unit type advantages.

        Returns:
            tuple: (list of P1 bonuses, list of P2 bonuses)
        """
        p1_advantages = set()
        p2_advantages = set()

        # Define strengths
        strengths = {
            UnitType.INFANTRY: UnitType.ARTILLERY,
            UnitType.ARTILLERY: UnitType.AIR,
            UnitType.AIR: UnitType.INFANTRY
        }

        # Check P1 advantages
        p1_types = set(unit.unit_type for unit in p1_units)
        p2_types = set(unit.unit_type for unit in p2_units)
        for ut in p1_types:
            if strengths[ut] not in p2_types:
                p1_advantages.add(f"{ut.name} advantage")

        # Check P2 advantages
        for ut in p2_types:
            if strengths[ut] not in p1_types:
                p2_advantages.add(f"{ut.name} advantage")

        return list(p1_advantages), list(p2_advantages)

    def perform_throws(self, y, p1_units, p2_units, p1_bonuses, p2_bonuses):
        """
        Perform throw-based combat resolution.

        Args:
            y (int): The row index where combat is occurring.
            p1_units (list): List of P1 units in combat.
            p2_units (list): List of P2 units in combat.
            p1_bonuses (list): List of P1 bonuses.
            p2_bonuses (list): List of P2 bonuses.
        """
        MAX_THROWS_PER_COMBAT = 9  # Updated as per user request

        # Calculate bonus modifiers
        p1_bonus_modifier = 0.0
        p2_bonus_modifier = 0.0
        for bonus in p1_bonuses:
            p1_bonus_modifier += 0.1  # Each bonus adds 10%
        for bonus in p2_bonuses:
            p2_bonus_modifier += 0.1  # Each bonus adds 10%

        for throw in range(MAX_THROWS_PER_COMBAT):
            if not p1_units or not p2_units:
                break

            # Determine attacker based on probabilities
            attack_prob = random.random()
            if attack_prob < (len(p1_units) / (len(p1_units) + len(p2_units))):
                attacker = 'P1'
                defender_units = p2_units
                bonus = p1_bonus_modifier
            else:
                attacker = 'P2'
                defender_units = p1_units
                bonus = p2_bonus_modifier

            # Calculate hit chance
            base_hit_chance = 0.5  # 50% base
            hit_chance = base_hit_chance + bonus
            hit_chance = min(hit_chance, 1.0)  # Cap at 100%

            # Determine if hit occurs
            if random.random() < hit_chance:
                # Hit occurs, remove a random unit from defender's pool
                if defender_units:
                    target_unit = random.choice(defender_units)
                    defender_units.remove(target_unit)
                    # Capture coordinates before removing
                    cell = self.grid.cells[target_unit.y][target_unit.x]
                    target_x, target_y = cell.remove_unit(target_unit)
                    print(f"{attacker} hits and removes a {target_unit.unit_type.name} at ({target_x}, {target_y})")
            else:
                print(f"{attacker} throws but misses.")

        # Determine combat outcome
        if p1_units and not p2_units:
            print(f"P1 wins combat at row {y}. Advancing frontline to the right.")
            self.grid.advance_frontline(y, direction=1)
        elif p2_units and not p1_units:
            print(f"P2 wins combat at row {y}. Advancing frontline to the left.")
            self.grid.advance_frontline(y, direction=-1)
        else:
            print(f"Combat at row {y} ended in a draw.")

    def calculate_areas(self):
        """Calculate the areas controlled by each player."""
        p1_area = sum(1 for row in self.grid.cells for cell in row if cell.player == 1)
        p2_area = sum(1 for row in self.grid.cells for cell in row if cell.player == 2)
        return p1_area, p2_area

    def reset_units_placement(self):
        """Reset the unit placement points for both players at the start of each turn."""
        self.player_points = {1: 10, 2: 10}  # Reset points; adjust as needed
        print("Unit placement points have been reset for both players.")