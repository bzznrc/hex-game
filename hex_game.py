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
        self.deploy_chunks_remaining = DEPLOY_CHUNKS_PER_TURN
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

    def deploy_chunk_to(self, q, r):
        if self.phase != PHASE_DEPLOYMENT:
            return False
        if self.deploy_chunks_remaining <= 0:
            return False
        if not self.grid.add_troops(q, r, self.active_player, UNITS_PER_DEPLOY_CHUNK):
            return False
        self.deploy_chunks_remaining -= 1
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
            if self.deploy_chunks_remaining > 0:
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
        self.deploy_chunks_remaining = DEPLOY_CHUNKS_PER_TURN
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
        crossing_river = self._is_river_crossing(source, target)
        topology = self.grid.frontline_topology(target.q, target.r)

        attacker_label = self._side_name(attacker)
        defender_label = self._side_name(defender)
        self._log(
            f"[COMBAT] TURN={self.turn} ATTACKER={attacker_label} DEFENDER={defender_label} "
            f"SRC=({source_q},{source_r}) TGT=({target_q},{target_r})"
        )
        self._log(f"[STATE] START_A={attacker_troops} START_D={defender_troops}")
        self._log_combat_context(crossing_river, target.terrain, topology)

        round_idx = 1
        while attacker_troops > 0 and defender_troops > 0:
            attacker_dice = min(3, attacker_troops)
            if crossing_river:
                attacker_dice -= 1
            if attacker_dice <= 0:
                self._log(f"[ROUND {round_idx}] STOP=NO_ATTACK_DICE")
                break

            defender_dice = self._defender_dice(defender_troops, target.terrain, topology)
            if defender_dice <= 0:
                defender_troops = 0
                self._log(f"[ROUND {round_idx}] STOP=NO_DEFENSE_DICE")
                break

            attacker_rolls = sorted((random.randint(1, 6) for _ in range(attacker_dice)), reverse=True)
            defender_rolls = sorted((random.randint(1, 6) for _ in range(defender_dice)), reverse=True)

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
                f"[ROUND {round_idx}] AD={attacker_dice} DD={defender_dice} "
                f"A_ROLLS={attacker_rolls} D_ROLLS={defender_rolls} "
                f"LOSS_A={attacker_losses} LOSS_D={defender_losses} "
                f"REM_A={attacker_troops} REM_D={defender_troops}"
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
            self._log(f"[RESULT] WINNER=ATTACKER OUTCOME=CAPTURE FINAL_A={attacker_troops} FINAL_D=0")
        else:
            self._log(
                f"[RESULT] WINNER=DEFENDER OUTCOME=HOLD FINAL_A={attacker_troops} "
                f"FINAL_D={defender_troops}"
            )
        return True

    def _is_river_crossing(self, source_cell, target_cell):
        return self.grid.has_river_between(
            source_cell.q,
            source_cell.r,
            target_cell.q,
            target_cell.r,
        )

    def _log_combat_context(self, crossing_river, defender_terrain, topology):
        if defender_terrain == TERRAIN_FOREST:
            self._log("[TERRAIN] FOREST=HIDDEN_UNITS_ONLY COMBAT_EFFECT=NONE")

        river_mod = -1 if crossing_river else 0
        self._log(f"[RIVER] ATTACK_DICE_MOD={river_mod}")

        if defender_terrain == TERRAIN_MOUNTAIN:
            if topology == "supported":
                self._log("[DEFENSE] TOPOLOGY=SUPPORTED(+1D) MOUNTAIN=+1D TOTAL_MOD=+2D")
            elif topology == "exposed":
                self._log("[DEFENSE] TOPOLOGY=EXPOSED(REPLACED_BY_MOUNTAIN) MOUNTAIN=+1D TOTAL_MOD=+1D")
            else:
                self._log("[DEFENSE] TOPOLOGY=NONE MOUNTAIN=+1D TOTAL_MOD=+1D")
            return

        if topology == "supported":
            self._log("[DEFENSE] TOPOLOGY=SUPPORTED(+1D) TOTAL_MOD=+1D")
        elif topology == "exposed":
            self._log("[DEFENSE] TOPOLOGY=EXPOSED(-1D) TOTAL_MOD=-1D")
        else:
            self._log("[DEFENSE] TOPOLOGY=NONE TOTAL_MOD=0")

    def _defender_dice(self, defender_troops, defender_terrain, topology):
        base = min(2, defender_troops)
        topology_mod = 0
        if topology == "supported":
            topology_mod = 1
        elif topology == "exposed":
            topology_mod = -1

        if defender_terrain == TERRAIN_MOUNTAIN and topology_mod < 0:
            topology_mod = 0
        mountain_mod = 1 if defender_terrain == TERRAIN_MOUNTAIN else 0

        return min(defender_troops, base + topology_mod + mountain_mod)

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
            self.deploy_chunk_to(q, r)
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
        for i in range(self.deploy_chunks_remaining):
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
        if self.deploy_chunks_remaining <= 0:
            self._drop_pending_cpu_actions("Deploy")
            return

        target = self._pick_ai_deploy_target()
        if target is None or not self.deploy_chunk_to(target.q, target.r):
            self.deploy_chunks_remaining = 0
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
            self._visible_enemy_troops(player, neighbor)
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
                defender_troops = self._visible_enemy_troops(OWNER_CPU, neighbor)
                if attacker_troops <= defender_troops:
                    continue
                score = (attacker_troops - defender_troops, defender_troops)
                if best is None or score > best_score:
                    best = (cell, neighbor)
                    best_score = score

        return best

    def _visible_enemy_troops(self, observer, enemy_cell):
        if enemy_cell.terrain == TERRAIN_FOREST:
            return 1
        enemy = self.grid.enemy_of(observer)
        return enemy_cell.troops_of(enemy)

    @staticmethod
    def _side_name(owner):
        return "PLAYER" if owner == OWNER_PLAYER else "CPU"
