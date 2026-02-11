import random
from constants import *


class HexGame:
    def __init__(self, grid):
        self.grid = grid
        self.turn = 1
        self.phase = PHASE_DEPLOYMENT
        self.active_player = OWNER_P1

        self.selected_source = None
        self.reinforcements_remaining = REINFORCEMENTS_PER_PLAYER
        self.attacks_used = 0
        self.last_combat_log = []

    def clear_selection(self):
        self.selected_source = None

    def select_source(self, q, r):
        cell = self.grid.get_cell(q, r)
        if cell is None:
            return False
        if cell.owner != self.active_player:
            return False
        if cell.troops_of(self.active_player) <= 0:
            return False

        self.selected_source = (q, r)
        return True

    def move_selected_to(self, q, r):
        if self.selected_source is None:
            return False
        if self.phase != PHASE_MOVEMENT:
            return False

        source_q, source_r = self.selected_source
        return self.grid.transfer_troop(source_q, source_r, q, r, self.active_player)

    def deploy_to(self, q, r):
        if self.phase != PHASE_DEPLOYMENT:
            return False
        if self.reinforcements_remaining <= 0:
            return False
        if not self.grid.add_troop(q, r, self.active_player):
            return False
        self.reinforcements_remaining -= 1
        return True

    def attack_selected_to(self, q, r):
        if self.selected_source is None:
            return False
        if self.phase != PHASE_ATTACK:
            return False
        if self.attacks_used >= MAX_ATTACKS_PER_TURN:
            return False

        source_q, source_r = self.selected_source
        if not self.grid.can_attack(source_q, source_r, q, r, self.active_player):
            return False

        if not self._resolve_manual_attack(source_q, source_r, q, r):
            return False

        self.attacks_used += 1
        self.clear_selection()
        return True

    def end_player_step(self):
        self.clear_selection()

        if self.phase == PHASE_DEPLOYMENT:
            if self.reinforcements_remaining > 0:
                return
            self.phase = PHASE_ATTACK
            self.attacks_used = 0
            self.last_combat_log = []
            return

        if self.phase == PHASE_ATTACK:
            self.phase = PHASE_MOVEMENT
            return

        if self.phase == PHASE_MOVEMENT:
            self._end_turn()

    def _end_turn(self):
        if self.active_player == OWNER_P1:
            self.active_player = OWNER_P2
        else:
            self.active_player = OWNER_P1
            self.turn += 1

        self.phase = PHASE_DEPLOYMENT
        self.reinforcements_remaining = REINFORCEMENTS_PER_PLAYER
        self.attacks_used = 0
        self.last_combat_log = []
        self.clear_selection()

    def _resolve_manual_attack(self, source_q, source_r, target_q, target_r):
        attacker = self.active_player
        defender = self.grid.enemy_of(attacker)

        source = self.grid.get_cell(source_q, source_r)
        target = self.grid.get_cell(target_q, target_r)
        if source is None or target is None:
            return False

        attacker_troops = source.troops_of(attacker)
        defender_troops = target.troops_of(defender)

        tag = f"T{self.turn} P{attacker} ({source_q},{source_r})->({target_q},{target_r})"
        self._log(f"[{tag}] start A:{attacker_troops} D:{defender_troops}")

        terrain_note = self._terrain_note(source.terrain, target.terrain)
        if terrain_note:
            self._log(f"[{tag}] terrain {terrain_note}")

        round_idx = 1
        while attacker_troops > 0 and defender_troops > 0:
            attacker_dice = min(3, attacker_troops)
            defender_dice = min(2, defender_troops)

            attacker_rolls = sorted(
                (random.randint(1, 6) for _ in range(attacker_dice)), reverse=True
            )
            defender_rolls = sorted(
                (random.randint(1, 6) for _ in range(defender_dice)), reverse=True
            )

            if source.terrain == TERRAIN_MOUNTAIN and attacker_rolls:
                attacker_rolls[0] = min(6, attacker_rolls[0] + 1)
            if target.terrain == TERRAIN_MOUNTAIN and defender_rolls:
                defender_rolls[0] = min(6, defender_rolls[0] + 1)
            if source.terrain == TERRAIN_RIVER and attacker_rolls:
                attacker_rolls[0] = max(1, attacker_rolls[0] - 1)
            if target.terrain == TERRAIN_RIVER and defender_rolls:
                defender_rolls[0] = max(1, defender_rolls[0] - 1)

            attacker_losses = 0
            defender_losses = 0
            for i in range(min(len(attacker_rolls), len(defender_rolls))):
                if attacker_rolls[i] > defender_rolls[i]:
                    defender_troops -= 1
                    defender_losses += 1
                else:
                    attacker_troops -= 1
                    attacker_losses += 1

            self._log(
                f"[{tag}] R{round_idx} A{attacker_rolls} vs D{defender_rolls} | "
                f"A-{attacker_losses} D-{defender_losses} | A:{attacker_troops} D:{defender_troops}"
            )
            round_idx += 1

        if not self.grid.apply_attack_result(
            source_q,
            source_r,
            target_q,
            target_r,
            attacker,
            attacker_troops,
            defender_troops,
        ):
            return False

        if defender_troops == 0 and attacker_troops > 0:
            self._log(f"[{tag}] result A wins, captures")
        else:
            self._log(f"[{tag}] result D holds")
        return True

    def _terrain_note(self, attacker_terrain, defender_terrain):
        notes = []
        if attacker_terrain == TERRAIN_MOUNTAIN:
            notes.append("attacker mountain +1")
        elif attacker_terrain == TERRAIN_RIVER:
            notes.append("attacker river -1")

        if defender_terrain == TERRAIN_MOUNTAIN:
            notes.append("defender mountain +1")
        elif defender_terrain == TERRAIN_RIVER:
            notes.append("defender river -1")
        return ", ".join(notes)

    def _log(self, message):
        self.last_combat_log.append(message)
        print(message)

    def handle_click(self, q, r, button):
        cell = self.grid.get_cell(q, r)
        if cell is None:
            return

        if button == 3:
            self.clear_selection()
            return

        if button != 1:
            return

        if self.phase == PHASE_DEPLOYMENT:
            self.clear_selection()
            self.deploy_to(q, r)
            return

        if self.selected_source is None:
            self.select_source(q, r)
            return

        if self.phase == PHASE_MOVEMENT:
            moved = self.move_selected_to(q, r)
            if not moved:
                self.select_source(q, r)
            return

        if self.phase == PHASE_ATTACK:
            attacked = self.attack_selected_to(q, r)
            if not attacked:
                self.select_source(q, r)
