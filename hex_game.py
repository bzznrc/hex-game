import random
from collections import deque
from constants import *


class HexGame:
    def __init__(self, grid):
        self.grid = grid
        self.turn = 1
        self.level = 1
        self.max_levels = CAMPAIGN_LEVELS
        self.phase = PHASE_DEPLOYMENT
        self.active_player = OWNER_PLAYER

        self.selected_source = None
        self.reinforcements_remaining = REINFORCEMENTS_PER_TURN
        self.attacks_used = 0
        self.last_combat_log = []
        self.cpu_action_delay = float(CPU_ACTION_DELAY_SECONDS)
        self.cpu_deploy_action_delay = float(CPU_DEPLOY_ACTION_DELAY_SECONDS)
        self.cpu_action_queue = deque()
        self.cpu_action_label = ""
        self.cpu_action_timer = 0.0

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

        if not self._resolve_attack(source_q, source_r, q, r):
            return False

        self.attacks_used += 1
        self.clear_selection()
        return True

    def end_player_step(self):
        if self.active_player != OWNER_PLAYER:
            return

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

    def update(self, dt_seconds):
        if self.active_player != OWNER_CPU:
            return
        if not self.cpu_action_queue:
            return

        self.cpu_action_timer = max(0.0, self.cpu_action_timer - max(0.0, dt_seconds))
        if self.cpu_action_timer > 0.0:
            return

        _, action = self.cpu_action_queue.popleft()
        action()
        self._prime_next_cpu_action()

    def _end_turn(self):
        if self.active_player == OWNER_PLAYER:
            self.active_player = OWNER_CPU
        else:
            self.active_player = OWNER_PLAYER
            self.turn += 1

        self.phase = PHASE_DEPLOYMENT
        self.reinforcements_remaining = REINFORCEMENTS_PER_TURN
        self.attacks_used = 0
        self.last_combat_log = []
        self.clear_selection()

        if self.active_player == OWNER_CPU:
            self._start_cpu_turn()

    def _resolve_attack(self, source_q, source_r, target_q, target_r):
        attacker = self.active_player
        defender = self.grid.enemy_of(attacker)

        source = self.grid.get_cell(source_q, source_r)
        target = self.grid.get_cell(target_q, target_r)
        if source is None or target is None:
            return False

        attacker_troops = source.troops_of(attacker)
        defender_troops = target.troops_of(defender)

        attacker_label = self._side_name(attacker)
        tag = f"T{self.turn} {attacker_label} ({source_q},{source_r})->({target_q},{target_r})"
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
        if self.active_player != OWNER_PLAYER:
            return

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

    def _start_cpu_turn(self):
        if self.active_player != OWNER_CPU:
            return

        self.cpu_action_queue.clear()
        for i in range(self.reinforcements_remaining):
            self.cpu_action_queue.append((f"Deploy {i + 1}", self._ai_deploy_step))
        for i in range(MAX_ATTACKS_PER_TURN):
            self.cpu_action_queue.append((f"Attack {i + 1}", self._ai_attack_step))
        self.cpu_action_queue.append(("End Turn", self._ai_end_turn_step))
        self._prime_next_cpu_action()

    def _prime_next_cpu_action(self):
        if self.active_player != OWNER_CPU or not self.cpu_action_queue:
            self.cpu_action_label = ""
            self.cpu_action_timer = 0.0
            return

        self.cpu_action_label = self.cpu_action_queue[0][0]
        if self.cpu_action_label.startswith("Deploy"):
            self.cpu_action_timer = self.cpu_deploy_action_delay
        else:
            self.cpu_action_timer = self.cpu_action_delay

    def _drop_pending_cpu_actions(self, prefix):
        self.cpu_action_queue = deque(
            (label, action)
            for label, action in self.cpu_action_queue
            if not label.startswith(prefix)
        )

    def _ai_deploy_step(self):
        self.phase = PHASE_DEPLOYMENT
        if self.reinforcements_remaining <= 0:
            self._drop_pending_cpu_actions("Deploy")
            return

        target = self._pick_ai_deploy_target()
        if target is None or not self.deploy_to(target.q, target.r):
            self.reinforcements_remaining = 0
            self._drop_pending_cpu_actions("Deploy")

    def _ai_attack_step(self):
        self.phase = PHASE_ATTACK
        if self.attacks_used >= MAX_ATTACKS_PER_TURN:
            self._drop_pending_cpu_actions("Attack")
            return

        attack = self._pick_ai_attack()
        if attack is None:
            self._drop_pending_cpu_actions("Attack")
            return

        source, target = attack
        if self._resolve_attack(source.q, source.r, target.q, target.r):
            self.attacks_used += 1
            self.clear_selection()
        else:
            self._drop_pending_cpu_actions("Attack")

    def _ai_end_turn_step(self):
        self.phase = PHASE_MOVEMENT
        self.cpu_action_queue.clear()
        self.cpu_action_label = ""
        self.cpu_action_timer = 0.0
        self._end_turn()

    def _pick_ai_deploy_target(self):
        frontline = self.grid.frontline_cells(OWNER_CPU)
        if frontline:
            frontline.sort(key=lambda c: self._enemy_pressure(c, OWNER_CPU), reverse=True)
            return frontline[0]

        owned = [c for c in self.grid.get_all_cells() if c.owner == OWNER_CPU]
        if not owned:
            return None
        owned.sort(key=lambda c: c.troops_of(OWNER_CPU))
        return owned[0]

    def _enemy_pressure(self, cell, player):
        enemy = self.grid.enemy_of(player)
        return sum(
            neighbor.troops_of(enemy)
            for neighbor in self.grid.get_neighbors(cell.q, cell.r)
            if neighbor.owner == enemy
        )

    def _pick_ai_attack(self):
        enemy = self.grid.enemy_of(OWNER_CPU)
        best = None
        best_score = None

        for cell in self.grid.get_all_cells():
            if cell.owner != OWNER_CPU:
                continue
            attacker_troops = cell.troops_of(OWNER_CPU)
            if attacker_troops <= 1:
                continue

            for neighbor in self.grid.get_neighbors(cell.q, cell.r):
                if neighbor.owner != enemy:
                    continue
                defender_troops = neighbor.troops_of(enemy)
                if attacker_troops <= defender_troops:
                    continue
                score = (attacker_troops - defender_troops, defender_troops)
                if best is None or score > best_score:
                    best = (cell, neighbor)
                    best_score = score

        return best

    @staticmethod
    def _side_name(owner):
        return "You" if owner == OWNER_PLAYER else "CPU"
