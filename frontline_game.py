import random
from constants import *


class FrontlineGame:
    def __init__(self, grid):
        self.grid = grid
        self.turn = 1

        self.phase = PHASE_MOVEMENT
        self.active_player = OWNER_P1

        self.reinforcements = {
            OWNER_P1: REINFORCEMENTS_PER_PLAYER,
            OWNER_P2: REINFORCEMENTS_PER_PLAYER,
        }
        self.move_actions = {
            OWNER_P1: MOVE_ACTIONS_PER_PLAYER,
            OWNER_P2: MOVE_ACTIONS_PER_PLAYER,
        }
        self.post_move_actions = {
            OWNER_P1: POST_MOVE_ACTIONS_PER_PLAYER,
            OWNER_P2: POST_MOVE_ACTIONS_PER_PLAYER,
        }

        self.selected_source = None
        self.row_winner = {}
        self.last_combat_log = []

    def place_reinforcement(self, q, r):
        if self.phase != PHASE_MOVEMENT:
            return False
        if self.reinforcements[self.active_player] <= 0:
            return False

        cell = self.grid.get_cell(q, r)
        if cell is None or cell.frontline:
            return False
        if cell.owner != self.active_player:
            return False

        ok = self.grid.add_troop(q, r, self.active_player)
        if not ok:
            return False
        self.reinforcements[self.active_player] -= 1
        return True

    def select_source(self, q, r):
        cell = self.grid.get_cell(q, r)
        if cell is None:
            return False
        if cell.troops_of(self.active_player) <= 1:
            return False
        self.selected_source = (q, r)
        return True

    def clear_selection(self):
        self.selected_source = None

    def move_selected_to(self, q, r):
        if self.selected_source is None:
            return False

        sq, sr = self.selected_source
        source = self.grid.get_cell(sq, sr)
        target = self.grid.get_cell(q, r)
        if source is None or target is None:
            return False
        if not self.grid.are_adjacent(sq, sr, q, r):
            return False

        if self.phase == PHASE_MOVEMENT:
            if self.move_actions[self.active_player] <= 0:
                return False
            if target.frontline:
                return False
            if target.owner != self.active_player:
                return False
            if source.troops_of(self.active_player) <= 1:
                return False
            if not self.grid.add_troop(q, r, self.active_player):
                return False
            self.grid.remove_troop(sq, sr, self.active_player)
            self.move_actions[self.active_player] -= 1
            return True

        if self.phase == PHASE_POST_MOVEMENT:
            if self.post_move_actions[self.active_player] <= 0:
                return False
            if not target.frontline:
                return False
            if self.row_winner.get(r) != self.active_player:
                return False
            if source.troops_of(self.active_player) <= 1:
                return False
            if not self.grid.add_troop(q, r, self.active_player):
                return False
            self.grid.remove_troop(sq, sr, self.active_player)
            self.post_move_actions[self.active_player] -= 1
            return True

        return False

    def end_player_step(self):
        self.clear_selection()

        if self.phase == PHASE_MOVEMENT:
            if self.active_player == OWNER_P1:
                self.active_player = OWNER_P2
            else:
                self.phase = PHASE_COMBAT
                self.resolve_combat()
                self.phase = PHASE_POST_MOVEMENT
                self.active_player = OWNER_P1
            return

        if self.phase == PHASE_POST_MOVEMENT:
            if self.active_player == OWNER_P1:
                self.active_player = OWNER_P2
            else:
                self.apply_frontline_shifts()
                self.start_next_turn()

    def start_next_turn(self):
        self.turn += 1
        self.phase = PHASE_MOVEMENT
        self.active_player = OWNER_P1
        self.reinforcements = {
            OWNER_P1: REINFORCEMENTS_PER_PLAYER,
            OWNER_P2: REINFORCEMENTS_PER_PLAYER,
        }
        self.move_actions = {
            OWNER_P1: MOVE_ACTIONS_PER_PLAYER,
            OWNER_P2: MOVE_ACTIONS_PER_PLAYER,
        }
        self.post_move_actions = {
            OWNER_P1: POST_MOVE_ACTIONS_PER_PLAYER,
            OWNER_P2: POST_MOVE_ACTIONS_PER_PLAYER,
        }
        self.row_winner = {}
        self.last_combat_log = []
        self.clear_selection()

    def resolve_combat(self):
        self.row_winner = {}
        self.last_combat_log = []

        for r in range(self.grid.rows):
            f_q = self.grid.frontline_q_by_row[r]
            left = self.grid.get_cell(f_q - 1, r)
            right = self.grid.get_cell(f_q + 1, r)

            if left is None or right is None:
                continue

            p1_troops = left.troops_of(OWNER_P1) if left.owner == OWNER_P1 else 0
            p2_troops = right.troops_of(OWNER_P2) if right.owner == OWNER_P2 else 0

            if p1_troops <= 0 and p2_troops <= 0:
                continue
            if p1_troops > 0 and p2_troops <= 0:
                self.row_winner[r] = OWNER_P1
                self.last_combat_log.append(f"r{r}: P1 wins uncontested")
                continue
            if p2_troops > 0 and p1_troops <= 0:
                self.row_winner[r] = OWNER_P2
                self.last_combat_log.append(f"r{r}: P2 wins uncontested")
                continue

            p1_remaining, p2_remaining = self._risk_battle(
                p1_troops, p2_troops, left.terrain, right.terrain
            )

            left.troops[OWNER_P1] = p1_remaining
            right.troops[OWNER_P2] = p2_remaining

            if p1_remaining > 0 and p2_remaining <= 0:
                self.row_winner[r] = OWNER_P1
                self.last_combat_log.append(f"r{r}: P1 {p1_remaining} vs 0")
            elif p2_remaining > 0 and p1_remaining <= 0:
                self.row_winner[r] = OWNER_P2
                self.last_combat_log.append(f"r{r}: P2 {p2_remaining} vs 0")
            else:
                self.last_combat_log.append(f"r{r}: draw {p1_remaining}-{p2_remaining}")

    def _risk_battle(self, p1_troops, p2_troops, p1_terrain, p2_terrain):
        rounds = 0
        while p1_troops > 0 and p2_troops > 0 and rounds < MAX_COMBAT_ROUNDS:
            p1_dice = min(3, p1_troops)
            p2_dice = min(2, p2_troops)

            p1_rolls = sorted((random.randint(1, 6) for _ in range(p1_dice)), reverse=True)
            p2_rolls = sorted((random.randint(1, 6) for _ in range(p2_dice)), reverse=True)

            if p1_terrain == TERRAIN_MOUNTAIN and p1_rolls:
                p1_rolls[0] = min(6, p1_rolls[0] + 1)
            if p2_terrain == TERRAIN_MOUNTAIN and p2_rolls:
                p2_rolls[0] = min(6, p2_rolls[0] + 1)

            if p1_terrain == TERRAIN_RIVER and p1_rolls:
                p1_rolls[0] = max(1, p1_rolls[0] - 1)
            if p2_terrain == TERRAIN_RIVER and p2_rolls:
                p2_rolls[0] = max(1, p2_rolls[0] - 1)

            comparisons = min(len(p1_rolls), len(p2_rolls))
            for i in range(comparisons):
                if p1_rolls[i] > p2_rolls[i]:
                    p2_troops -= 1
                else:
                    p1_troops -= 1

            rounds += 1

        return max(0, p1_troops), max(0, p2_troops)

    def apply_frontline_shifts(self):
        for r in range(self.grid.rows):
            if self.row_winner.get(r) not in (OWNER_P1, OWNER_P2):
                continue
            f_q = self.grid.frontline_q_by_row[r]
            front = self.grid.get_cell(f_q, r)

            if front is None:
                continue
            if front.troops_of(OWNER_P1) > 0 and front.troops_of(OWNER_P2) == 0:
                self.grid.shift_frontline_row(r, direction=1)
            elif front.troops_of(OWNER_P2) > 0 and front.troops_of(OWNER_P1) == 0:
                self.grid.shift_frontline_row(r, direction=-1)

    def handle_click(self, q, r, button):
        cell = self.grid.get_cell(q, r)
        if cell is None:
            return

        if button == 3:
            self.clear_selection()
            return

        if button != 1:
            return

        if self.selected_source is None:
            if self.phase == PHASE_MOVEMENT and self.place_reinforcement(q, r):
                return
            self.select_source(q, r)
            return

        moved = self.move_selected_to(q, r)
        if not moved:
            self.select_source(q, r)
