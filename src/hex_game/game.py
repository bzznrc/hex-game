import random
from collections import deque

from hex_game.config import (
    CAMPAIGN_LEVELS,
    COMBAT_BASE_ATTACKER_CHANCE,
    COMBAT_EXPOSED_DEFENDER_ATTACKER_DELTA,
    COMBAT_GLOBAL_DEFENDER_BIAS_ATTACKER_DELTA,
    COMBAT_MAX_ATTACKER_CHANCE,
    COMBAT_MIN_ATTACKER_CHANCE,
    COMBAT_MOUNTAIN_DEFENDER_ATTACKER_DELTA,
    COMBAT_RIVER_CROSSING_ATTACKER_DELTA,
    CPU_ACTION_DELAY_SECONDS,
    CPU_DEPLOY_ACTION_DELAY_SECONDS,
    DEPLOY_CHUNKS_PER_TURN,
    MAX_MOVEMENT_SOURCE_HEXES,
    OWNER_CPU,
    OWNER_PLAYER,
    PHASE_ATTACK,
    PHASE_DEPLOYMENT,
    PHASE_MOVEMENT,
    TERRAIN_FOREST,
    TERRAIN_MOUNTAIN,
    UNITS_PER_DEPLOY_CHUNK,
)
from hex_game.grid import HexGrid

class HexGame:
    def __init__(self, grid):
        self.grid = grid
        self.turn = 1
        self.level = 1
        self.max_levels = CAMPAIGN_LEVELS
        self.phase = PHASE_DEPLOYMENT
        self.first_turn_first_player = random.choice((OWNER_PLAYER, OWNER_CPU))
        self.active_player = self.first_turn_first_player
        self.game_over = False
        self.campaign_won = False

        self.selected_source = None
        self.deploy_chunks_total = 0
        self.deploy_units_total = 0
        self.deploy_units_remaining = 0
        self.deploy_chunks_remaining = 0
        self.deploy_placements = {}
        self.movement_sources_used = set()
        self.last_combat_log = []
        self.cpu_action_delay = float(CPU_ACTION_DELAY_SECONDS)
        self.cpu_deploy_action_delay = float(CPU_DEPLOY_ACTION_DELAY_SECONDS)
        self.cpu_action_queue = deque()
        self.cpu_action_label = ""
        self.cpu_action_timer = 0.0
        self._reset_deployment_budget()

        if self.active_player == OWNER_CPU:
            self._start_cpu_turn()

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
        if self.phase == PHASE_MOVEMENT:
            coord = (q, r)
            if (
                coord not in self.movement_sources_used
                and len(self.movement_sources_used) >= int(MAX_MOVEMENT_SOURCE_HEXES)
            ):
                return False

        self.selected_source = (q, r)
        return True

    def move_selected_to(self, q, r):
        if self.selected_source is None:
            return False
        if self.phase != PHASE_MOVEMENT:
            return False

        source_q, source_r = self.selected_source
        source_coord = (source_q, source_r)
        if (
            source_coord not in self.movement_sources_used
            and len(self.movement_sources_used) >= int(MAX_MOVEMENT_SOURCE_HEXES)
        ):
            return False

        moved = self.grid.transfer_troop(source_q, source_r, q, r, self.active_player)
        if moved:
            self.movement_sources_used.add(source_coord)
        return moved

    def deploy_chunk_to(self, q, r):
        if self.phase != PHASE_DEPLOYMENT:
            return False
        if self.deploy_units_remaining <= 0:
            return False
        cell = self.grid.get_cell(q, r)
        if cell is None:
            return False
        if not self.grid.can_deploy_to_cell(q, r, self.active_player):
            return False

        free_capacity = self._deploy_capacity_at(q, r)
        deploy_count = min(
            int(UNITS_PER_DEPLOY_CHUNK),
            int(self.deploy_units_remaining),
            int(free_capacity),
        )
        if deploy_count <= 0:
            return False
        if not self.grid.add_troops(q, r, self.active_player, deploy_count):
            return False

        self.deploy_units_remaining -= deploy_count
        self._sync_deploy_chunks_remaining()
        coord = (q, r)
        self.deploy_placements.setdefault(coord, []).append(deploy_count)
        return True

    def undo_deploy_chunk_from(self, q, r):
        if self.phase != PHASE_DEPLOYMENT:
            return False
        coord = (q, r)
        placed = self.deploy_placements.get(coord, [])
        if not placed:
            return False
        remove_count = int(placed[-1])
        if not self.grid.remove_troops(q, r, self.active_player, remove_count):
            return False

        placed.pop()
        if not placed:
            self.deploy_placements.pop(coord, None)
        self.deploy_units_remaining = min(
            int(self.deploy_units_total),
            int(self.deploy_units_remaining) + remove_count,
        )
        self._sync_deploy_chunks_remaining()
        return True

    def attack_selected_to(self, q, r):
        if self.selected_source is None:
            return False
        if self.phase != PHASE_ATTACK:
            return False

        source_q, source_r = self.selected_source
        if not self.grid.can_attack(source_q, source_r, q, r, self.active_player):
            return False

        if not self._resolve_attack(source_q, source_r, q, r):
            return False

        if self.game_over or self.phase != PHASE_ATTACK or self.active_player != OWNER_PLAYER:
            self.clear_selection()
            return True

        self.clear_selection()
        return True

    def end_player_step(self):
        if self.game_over:
            return
        if self.active_player != OWNER_PLAYER:
            return

        self.clear_selection()

        if self.phase == PHASE_DEPLOYMENT:
            if self.deploy_units_remaining > 0:
                if self._has_deploy_capacity(self.active_player):
                    return
                self.deploy_units_remaining = 0
                self._sync_deploy_chunks_remaining()
            self.phase = PHASE_ATTACK
            self.deploy_placements = {}
            self.last_combat_log = []
            return

        if self.phase == PHASE_ATTACK:
            self.phase = PHASE_MOVEMENT
            self.movement_sources_used = set()
            return

        if self.phase == PHASE_MOVEMENT:
            self._end_turn()

    def update(self, dt_seconds):
        if self.game_over:
            return
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
        current_player = self.active_player
        if current_player == self.first_turn_first_player:
            next_player = self.grid.enemy_of(current_player)
        else:
            next_player = self.first_turn_first_player
            self.turn += 1

        self.active_player = next_player

        self.phase = PHASE_DEPLOYMENT
        self._reset_deployment_budget()
        self.deploy_placements = {}
        self.movement_sources_used = set()
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
        start_attacker_troops = attacker_troops
        start_defender_troops = defender_troops
        crossing_river = self._is_river_crossing(source, target)
        topology = self.grid.frontline_topology(target.q, target.r)
        attacker_chance, modifier_lines = self._attacker_round_chance(
            crossing_river,
            target.terrain,
            topology,
        )

        attacker_label = self._side_name(attacker)
        defender_label = self._side_name(defender)
        self._log(
            f"Attack: {attacker_label} -> {defender_label} | "
            f"Src: [{source_q},{source_r}] & Tgt: [{target_q},{target_r}]"
        )
        self._log("Modifiers:")
        for line in modifier_lines:
            self._log(f"  - {line}")

        self._log("Turns:")
        round_idx = 1
        while attacker_troops > 0 and defender_troops > 0:
            draw = random.random()
            if draw < attacker_chance:
                defender_troops -= 1
                casualty = "Defender -1"
            else:
                attacker_troops -= 1
                casualty = "Attacker -1"

            self._log(
                f"  - T{round_idx}: Draw {draw:.2f} | "
                f"A {self._pct(attacker_chance)} -> {casualty} | "
                f"Remaining {attacker_troops}-{defender_troops}"
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

        outcome = "Win" if defender_troops == 0 and attacker_troops > 0 else "Loss"
        winner = attacker_label if outcome == "Win" else defender_label
        self._log(
            f"Result: {outcome} | Winner: {winner} | "
            f"Start: {start_attacker_troops}-{start_defender_troops} | "
            f"End: {attacker_troops}-{defender_troops}"
        )

        if self._is_enemy_capital_captured(attacker, defender):
            if attacker == OWNER_PLAYER:
                self._log("Capital: Captured CPU capital")
                self._on_player_level_win()
            else:
                self._log("Capital: CPU captured your capital")
                self._set_game_over(campaign_won=False)

        return True

    def _is_river_crossing(self, source_cell, target_cell):
        return self.grid.has_river_between(
            source_cell.q,
            source_cell.r,
            target_cell.q,
            target_cell.r,
        )

    def _attacker_round_chance(self, crossing_river, defender_terrain, topology):
        chance = COMBAT_BASE_ATTACKER_CHANCE
        lines = [f"Base: Attacker {self._pct(chance)} | Defender {self._pct(1.0 - chance)}"]

        if COMBAT_GLOBAL_DEFENDER_BIAS_ATTACKER_DELTA != 0:
            chance += COMBAT_GLOBAL_DEFENDER_BIAS_ATTACKER_DELTA
            lines.append(
                "Global Defender Bias: "
                f"Attacker {self._signed_pct(COMBAT_GLOBAL_DEFENDER_BIAS_ATTACKER_DELTA)}"
            )

        if defender_terrain == TERRAIN_MOUNTAIN:
            chance += COMBAT_MOUNTAIN_DEFENDER_ATTACKER_DELTA
            lines.append(
                "Mountain Defender: "
                f"Attacker {self._signed_pct(COMBAT_MOUNTAIN_DEFENDER_ATTACKER_DELTA)}"
            )

        if crossing_river:
            chance += COMBAT_RIVER_CROSSING_ATTACKER_DELTA
            lines.append(
                "River Crossing: "
                f"Attacker {self._signed_pct(COMBAT_RIVER_CROSSING_ATTACKER_DELTA)}"
            )

        if topology == "exposed":
            chance += COMBAT_EXPOSED_DEFENDER_ATTACKER_DELTA
            lines.append(
                "Exposed Defender: "
                f"Attacker {self._signed_pct(COMBAT_EXPOSED_DEFENDER_ATTACKER_DELTA)}"
            )

        if defender_terrain == TERRAIN_FOREST:
            lines.append("Forest: Hidden units (no chance modifier)")

        unclamped = chance
        chance = max(COMBAT_MIN_ATTACKER_CHANCE, min(COMBAT_MAX_ATTACKER_CHANCE, chance))
        if chance != unclamped:
            lines.append(
                f"Clamp: Attacker {self._pct(unclamped)} -> {self._pct(chance)}"
            )

        lines.append(f"Final: Attacker {self._pct(chance)} | Defender {self._pct(1.0 - chance)}")
        return chance, lines

    @staticmethod
    def _pct(value):
        return f"{int(round(value * 100))}%"

    @staticmethod
    def _signed_pct(value):
        sign = "+" if value >= 0 else ""
        return f"{sign}{int(round(value * 100))}%"

    def _log(self, message):
        self.last_combat_log.append(message)
        print(message)

    def handle_click(self, q, r, button):
        if self.game_over:
            return
        if self.active_player != OWNER_PLAYER:
            return

        cell = self.grid.get_cell(q, r)
        if cell is None:
            return

        if button == 3:
            if self.phase == PHASE_DEPLOYMENT:
                self.undo_deploy_chunk_from(q, r)
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
        if self.game_over:
            return
        if self.active_player != OWNER_CPU:
            return

        self.cpu_action_queue.clear()
        if self.deploy_units_remaining > 0:
            self.cpu_action_queue.append(("Deploy", self._ai_deploy_step))
        self.cpu_action_queue.append(("Attack", self._ai_attack_step))
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
        if self.deploy_units_remaining <= 0:
            self._drop_pending_cpu_actions("Deploy")
            return

        for target in self._iter_ai_deploy_targets():
            if self.deploy_chunk_to(target.q, target.r):
                if self.deploy_units_remaining > 0:
                    self.cpu_action_queue.appendleft(("Deploy", self._ai_deploy_step))
                else:
                    self._drop_pending_cpu_actions("Deploy")
                return

        self.deploy_units_remaining = 0
        self._sync_deploy_chunks_remaining()
        self._drop_pending_cpu_actions("Deploy")

    def _sync_deploy_chunks_remaining(self):
        units_per_chunk = max(1, int(UNITS_PER_DEPLOY_CHUNK))
        if self.deploy_units_remaining <= 0:
            self.deploy_chunks_remaining = 0
            return
        self.deploy_chunks_remaining = (
            int(self.deploy_units_remaining) + units_per_chunk - 1
        ) // units_per_chunk

    def _reset_deployment_budget(self):
        units_per_chunk = max(1, int(UNITS_PER_DEPLOY_CHUNK))
        full_chunks = self._deploy_chunks_for(self.active_player)
        full_units = int(full_chunks) * units_per_chunk
        if self.turn == 1 and self.active_player == self.first_turn_first_player:
            self.deploy_units_total = max(1, full_units // 2)
        else:
            self.deploy_units_total = full_units
        self.deploy_chunks_total = (
            int(self.deploy_units_total) + units_per_chunk - 1
        ) // units_per_chunk
        self.deploy_units_remaining = self.deploy_units_total
        self._sync_deploy_chunks_remaining()
        self.deploy_placements = {}

    def _deploy_capacity_at(self, q, r):
        cell = self.grid.get_cell(q, r)
        if cell is None:
            return 0
        cap = self.grid.troop_cap_at(q, r)
        return max(0, int(cap) - int(cell.total_troops()))

    def _has_deploy_capacity(self, player):
        for cell in self.grid.get_all_cells():
            if not self.grid.can_deploy_to_cell(cell.q, cell.r, player):
                continue
            if self._deploy_capacity_at(cell.q, cell.r) > 0:
                return True
        return False

    def _iter_ai_deploy_targets(self):
        frontline = [
            c
            for c in self.grid.frontline_cells(OWNER_CPU)
            if self.grid.can_deploy_to_cell(c.q, c.r, OWNER_CPU)
            and self._deploy_capacity_at(c.q, c.r) > 0
        ]
        frontline.sort(key=self._ai_deploy_priority, reverse=True)

        owned = [
            c
            for c in self.grid.get_all_cells()
            if c.owner == OWNER_CPU
            and self.grid.can_deploy_to_cell(c.q, c.r, OWNER_CPU)
            and self._deploy_capacity_at(c.q, c.r) > 0
        ]
        owned.sort(key=lambda c: c.troops_of(OWNER_CPU))

        ordered = []
        seen = set()
        for cell in frontline + owned:
            coord = (cell.q, cell.r)
            if coord in seen:
                continue
            seen.add(coord)
            ordered.append(cell)
        return ordered

    def _pick_ai_deploy_target(self):
        targets = self._iter_ai_deploy_targets()
        if not targets:
            return None
        return targets[0]

    def _ai_attack_step(self):
        self.phase = PHASE_ATTACK
        attack = self._pick_ai_attack()
        if attack is None:
            self._drop_pending_cpu_actions("Attack")
            return

        source, target = attack
        if self._resolve_attack(source.q, source.r, target.q, target.r):
            if self.game_over or self.phase != PHASE_ATTACK or self.active_player != OWNER_CPU:
                return
            self.clear_selection()
            self.cpu_action_queue.appendleft(("Attack", self._ai_attack_step))
        else:
            self._drop_pending_cpu_actions("Attack")

    def _deploy_chunks_for(self, player):
        return int(DEPLOY_CHUNKS_PER_TURN) + int(self.grid.deployment_bonus_chunks(player))

    def _is_enemy_capital_captured(self, attacker, defender):
        capital = self.grid.capital_coord(defender)
        if capital is None:
            return False
        cell = self.grid.get_cell(capital[0], capital[1])
        if cell is None:
            return False
        return cell.owner == attacker

    def _on_player_level_win(self):
        if self.level >= self.max_levels:
            self._log("Campaign: Completed all games")
            self._set_game_over(campaign_won=True)
            return

        self.level += 1
        self._log(f"Campaign: Advancing to Game {self.level}/{self.max_levels}")
        self._reset_for_new_level()

    def _reset_for_new_level(self):
        self.grid = HexGrid(*HexGrid.compute_grid_size())
        self.turn = 1
        self.active_player = self.first_turn_first_player
        self.phase = PHASE_DEPLOYMENT
        self._reset_deployment_budget()
        self.movement_sources_used = set()
        self.last_combat_log = []
        self.clear_selection()
        self.cpu_action_queue.clear()
        self.cpu_action_label = ""
        self.cpu_action_timer = 0.0

        if self.active_player == OWNER_CPU:
            self._start_cpu_turn()

    def _set_game_over(self, campaign_won):
        self.game_over = True
        self.campaign_won = bool(campaign_won)
        self.phase = "Game Over"
        self.cpu_action_queue.clear()
        self.cpu_action_label = ""
        self.cpu_action_timer = 0.0

    def _ai_end_turn_step(self):
        self.phase = PHASE_MOVEMENT
        self.cpu_action_queue.clear()
        self.cpu_action_label = ""
        self.cpu_action_timer = 0.0
        self._end_turn()

    def _enemy_pressure(self, cell, player):
        enemy = self.grid.enemy_of(player)
        return sum(
            self._visible_enemy_troops(player, neighbor)
            for neighbor in self.grid.get_neighbors(cell.q, cell.r)
            if neighbor.owner == enemy
        )

    def _pick_ai_attack(self):
        candidates = self._ai_attack_candidates()
        if not candidates:
            return None

        # If the capital is reasonably vulnerable now, strike it directly.
        capital_strike = [candidate for candidate in candidates if candidate["is_enemy_capital"] and candidate["win_prob"] >= 0.58]
        if capital_strike:
            best = max(
                capital_strike,
                key=lambda candidate: (
                    candidate["win_prob"],
                    candidate["advantage"],
                    -candidate["distance_to_enemy_capital"],
                ),
            )
            return best["source"], best["target"]

        # Otherwise prioritize practical town captures to build future deployment advantage.
        town_push = [candidate for candidate in candidates if candidate["is_enemy_town"] and candidate["win_prob"] >= 0.45]
        if town_push:
            best = max(
                town_push,
                key=lambda candidate: (
                    candidate["win_prob"],
                    candidate["advantage"],
                    -candidate["distance_to_enemy_capital"],
                ),
            )
            return best["source"], best["target"]

        # Fallback: best local breakthrough based on convenience and strategic direction.
        best = max(
            candidates,
            key=lambda candidate: (
                candidate["score"],
                candidate["win_prob"],
                candidate["advantage"],
            ),
        )
        return best["source"], best["target"]

    def _ai_deploy_priority(self, cell):
        enemy = self.grid.enemy_of(OWNER_CPU)
        adjacent_enemies = [
            neighbor
            for neighbor in self.grid.get_neighbors(cell.q, cell.r)
            if neighbor.owner == enemy
        ]
        adjacent_capital = any(self.grid.is_capital_coord(neighbor.q, neighbor.r) for neighbor in adjacent_enemies)
        adjacent_town = any(
            self.grid.is_town_coord(neighbor.q, neighbor.r) and not self.grid.is_capital_coord(neighbor.q, neighbor.r)
            for neighbor in adjacent_enemies
        )
        pressure = self._enemy_pressure(cell, OWNER_CPU)
        return (
            1 if adjacent_capital else 0,
            1 if adjacent_town else 0,
            pressure,
            -cell.troops_of(OWNER_CPU),
        )

    def _ai_attack_candidates(self):
        enemy = self.grid.enemy_of(OWNER_CPU)
        enemy_capital = self.grid.capital_coord(enemy)
        candidates = []

        for source in self.grid.get_all_cells():
            if source.owner != OWNER_CPU:
                continue
            attacker_troops = source.troops_of(OWNER_CPU)
            if attacker_troops <= 1:
                continue

            for target in self.grid.get_neighbors(source.q, source.r):
                if target.owner != enemy:
                    continue

                defender_troops = max(0, int(self._visible_enemy_troops(OWNER_CPU, target)))
                crossing_river = self._is_river_crossing(source, target)
                topology = self.grid.frontline_topology(target.q, target.r)
                attacker_round_chance, _ = self._attacker_round_chance(
                    crossing_river,
                    target.terrain,
                    topology,
                )
                win_prob = self._attack_win_probability(
                    attacker_troops=attacker_troops,
                    defender_troops=defender_troops,
                    attacker_round_chance=attacker_round_chance,
                )
                distance_to_enemy_capital = (
                    HexGrid._hex_distance((target.q, target.r), enemy_capital)
                    if enemy_capital is not None
                    else 0
                )
                is_enemy_capital = self.grid.is_capital_coord(target.q, target.r)
                is_enemy_town = self.grid.is_town_coord(target.q, target.r) and not is_enemy_capital
                assumed_defenders = max(1, defender_troops)
                advantage = attacker_troops - assumed_defenders

                score = (
                    win_prob * 100.0
                    + advantage * 6.0
                    - distance_to_enemy_capital * 1.2
                    + (20.0 if is_enemy_capital else 0.0)
                    + (8.0 if is_enemy_town else 0.0)
                )

                candidates.append(
                    {
                        "source": source,
                        "target": target,
                        "win_prob": win_prob,
                        "advantage": advantage,
                        "distance_to_enemy_capital": distance_to_enemy_capital,
                        "is_enemy_capital": is_enemy_capital,
                        "is_enemy_town": is_enemy_town,
                        "score": score,
                    }
                )

        return candidates

    @staticmethod
    def _attack_win_probability(attacker_troops, defender_troops, attacker_round_chance):
        attacker = max(0, int(attacker_troops))
        defender = max(0, int(defender_troops))
        if defender <= 0:
            return 1.0
        if attacker <= 0:
            return 0.0

        p = max(0.0, min(1.0, float(attacker_round_chance)))
        dp = [[0.0 for _ in range(defender + 1)] for _ in range(attacker + 1)]
        for a in range(attacker + 1):
            dp[a][0] = 1.0
        for d in range(1, defender + 1):
            dp[0][d] = 0.0

        for a in range(1, attacker + 1):
            for d in range(1, defender + 1):
                dp[a][d] = p * dp[a][d - 1] + (1.0 - p) * dp[a - 1][d]

        return dp[attacker][defender]

    def _visible_enemy_troops(self, observer, enemy_cell):
        if enemy_cell.terrain == TERRAIN_FOREST:
            return 1
        enemy = self.grid.enemy_of(observer)
        return enemy_cell.troops_of(enemy)

    @staticmethod
    def _side_name(owner):
        return "You" if owner == OWNER_PLAYER else "CPU"


