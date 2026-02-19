import math
import random
from collections import deque
from itertools import combinations

from hex_game.config import (
    BB_HEIGHT,
    CITIES_PER_PLAYER,
    CITY_MIN_FRONTLINE_DISTANCE,
    CITY_MIN_PAIR_DISTANCE,
    CITY_PLACEMENT_MAX_COMBINATIONS,
    CITY_SPACING_MARGIN,
    COMBAT_EXPOSED_DEFENDER_ATTACKER_DELTA,
    DEPLOY_BONUS_CHUNKS_PER_SUPPLIED_TOWN,
    MAX_FOREST_CLUSTERS,
    MAX_FORESTS_PER_CLUSTER,
    MAX_MOUNTAIN_CLUSTERS,
    MAX_MOUNTAINS_PER_CLUSTER,
    MAX_RIVERS,
    MIN_FOREST_CLUSTERS,
    MIN_MOUNTAIN_CLUSTERS,
    MIN_RIVERS,
    OWNER_CPU,
    OWNER_NEUTRAL,
    OWNER_P1,
    OWNER_P2,
    OWNER_PLAYER,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TARGET_HEX_COUNT,
    TERRAIN_FOREST,
    TERRAIN_MOUNTAIN,
    TERRAIN_PLAIN,
    TROOP_CAP_MOUNTAIN,
    TROOP_CAP_PLAIN_FOREST,
    TROOP_CAP_TOWN,
)
from hex_game.generation import (
    collect_adjacency_edges,
    collect_boundary_coords,
    generate_boundary_crossing_edges,
    generate_clustered_regions,
    normalize_cluster_config,
    normalize_range_config,
)
from hex_game.layout import axial_to_pixel_odd_q, compute_best_fit_hex_layout, neighbor_coords_odd_q

class HexCell:
    def __init__(self, q, r):
        self.q = q
        self.r = r
        self.owner = OWNER_NEUTRAL
        self.terrain = TERRAIN_PLAIN
        self.troops = {
            OWNER_P1: 0,
            OWNER_P2: 0,
        }

    def troops_of(self, player):
        return self.troops[player]

    def total_troops(self):
        return self.troops[OWNER_P1] + self.troops[OWNER_P2]

class HexGrid:
    def __init__(
        self,
        cols,
        rows,
        hex_radius,
        board_origin_x,
        board_origin_y,
        bottom_bar_height,
    ):
        if cols < 2:
            raise ValueError("Grid needs at least 2 columns.")
        if rows < 1:
            raise ValueError("Grid needs at least 1 row.")
        if (cols * rows) % 2 != 0:
            raise ValueError("Grid area must be even to split into equal halves.")
        if hex_radius < 6:
            raise ValueError("Hex radius is too small.")

        self.cols = cols
        self.rows = rows
        self.hex_radius = hex_radius
        self.board_origin_x = board_origin_x
        self.board_origin_y = board_origin_y
        self.bottom_bar_height = bottom_bar_height
        self.cells = [[HexCell(q, r) for r in range(rows)] for q in range(cols)]

        # Used for initial balanced split generation only.
        self.ownership_cut_by_row = self._generate_ownership_cut_by_row()
        # Runtime boundary representation: edges between opposing neighbors.
        self.boundary_edges = set()
        # River representation: edges between adjacent cells.
        self.river_edges = set()
        # Cached coordinates of owner cells disconnected from their own capital.
        self._encircled_cells_cache = None
        # Cached in-supply cells by owner (connected to own capital).
        self._supply_reach_cache = {}
        # Fixed settlement coordinates by original owner.
        self.capitals = {}
        self.towns_by_origin = {
            OWNER_PLAYER: set(),
            OWNER_CPU: set(),
        }
        self.town_coords_set = set()

        self._assign_side_ownership_from_cut()
        self._rebuild_boundary_edges()
        try:
            self._assign_cities()
            self._generate_terrain()
        except ValueError as exc:
            self._abort_generation(str(exc))
        self.validate_integrity()

    @staticmethod
    def compute_bottom_bar_height():
        return BB_HEIGHT

    @staticmethod
    def compute_grid_size():
        layout = compute_best_fit_hex_layout(
            screen_width_px=SCREEN_WIDTH,
            screen_height_px=SCREEN_HEIGHT,
            bottom_bar_height_px=HexGrid.compute_bottom_bar_height(),
            target_hex_count=TARGET_HEX_COUNT,
        )
        return layout.as_tuple()

    @staticmethod
    def enemy_of(player):
        return OWNER_CPU if player == OWNER_PLAYER else OWNER_PLAYER

    @staticmethod
    def _abort_generation(message):
        print(f"Spawn configuration impossible: {message}")
        raise SystemExit(1)

    def _cell_troop_cap(self, q, r):
        if self.is_town_coord(q, r):
            return TROOP_CAP_TOWN
        cell = self.get_cell(q, r)
        if cell is None:
            return 0
        if cell.terrain == TERRAIN_MOUNTAIN:
            return TROOP_CAP_MOUNTAIN
        return TROOP_CAP_PLAIN_FOREST

    def troop_cap_at(self, q, r):
        return self._cell_troop_cap(q, r)

    def _clamp_troops_to_cell_cap(self, value, q, r):
        return max(0, min(self._cell_troop_cap(q, r), int(value)))

    def axial_to_pixel(self, q, r):
        return axial_to_pixel_odd_q(
            q=q,
            r=r,
            radius_px=self.hex_radius,
            origin_x_px=self.board_origin_x,
            origin_y_px=self.board_origin_y,
        )

    def get_cell(self, q, r):
        if 0 <= q < self.cols and 0 <= r < self.rows:
            return self.cells[q][r]
        return None

    def get_all_cells(self):
        return [cell for col in self.cells for cell in col]

    def get_neighbors(self, q, r):
        neighbors = []
        for neighbor_q, neighbor_r in neighbor_coords_odd_q(q, r):
            cell = self.get_cell(neighbor_q, neighbor_r)
            if cell is not None:
                neighbors.append(cell)
        return neighbors

    def are_adjacent(self, q1, r1, q2, r2):
        return any(n.q == q2 and n.r == r2 for n in self.get_neighbors(q1, r1))

    @staticmethod
    def _offset_to_cube(q, r):
        x = q
        z = r - ((q - (q & 1)) // 2)
        y = -x - z
        return x, y, z

    @classmethod
    def _hex_distance(cls, a, b):
        ax, ay, az = cls._offset_to_cube(a[0], a[1])
        bx, by, bz = cls._offset_to_cube(b[0], b[1])
        return max(abs(ax - bx), abs(ay - by), abs(az - bz))

    @staticmethod
    def _edge_key(a, b):
        return (a, b) if a < b else (b, a)

    def add_troop(self, q, r, player):
        return self.add_troops(q, r, player, 1)

    def add_troops(self, q, r, player, count):
        count = int(count)
        if count <= 0:
            return False

        cell = self.get_cell(q, r)
        if not self.can_deploy_to_cell(q, r, player):
            return False
        if cell.total_troops() + count > self._cell_troop_cap(q, r):
            return False

        cell.troops[player] += count
        self.validate_integrity()
        return True

    def remove_troops(self, q, r, player, count):
        count = int(count)
        if count <= 0:
            return False

        cell = self.get_cell(q, r)
        if cell is None or cell.owner != player:
            return False

        enemy = self.enemy_of(player)
        if cell.troops[enemy] > 0:
            return False
        if cell.troops[player] < count:
            return False

        cell.troops[player] -= count
        self.validate_integrity()
        return True

    def can_deploy_to_cell(self, q, r, player):
        cell = self.get_cell(q, r)
        if cell is None or cell.owner != player:
            return False

        enemy = self.enemy_of(player)
        if cell.troops[enemy] > 0:
            return False

        return self.in_supply(q, r, player)

    def transfer_troop(self, source_q, source_r, target_q, target_r, player):
        if not self.are_adjacent(source_q, source_r, target_q, target_r):
            return False

        source = self.get_cell(source_q, source_r)
        target = self.get_cell(target_q, target_r)
        if source is None or target is None:
            return False
        if source.owner != player or target.owner != player:
            return False
        if source.troops[player] <= 0:
            return False
        if target.total_troops() >= self._cell_troop_cap(target_q, target_r):
            return False
        enemy = self.enemy_of(player)
        if source.troops[enemy] > 0 or target.troops[enemy] > 0:
            return False

        source.troops[player] -= 1
        target.troops[player] += 1
        self.validate_integrity()
        return True

    def can_attack(self, source_q, source_r, target_q, target_r, attacker):
        if not self.are_adjacent(source_q, source_r, target_q, target_r):
            return False
        source = self.get_cell(source_q, source_r)
        target = self.get_cell(target_q, target_r)
        if source is None or target is None:
            return False
        if source.owner != attacker:
            return False
        defender = self.enemy_of(attacker)
        if target.owner != defender:
            return False
        if source.troops[attacker] <= 0:
            return False
        return True

    def apply_attack_result(
        self,
        source_q,
        source_r,
        target_q,
        target_r,
        attacker,
        attacker_remaining,
        defender_remaining,
    ):
        source = self.get_cell(source_q, source_r)
        target = self.get_cell(target_q, target_r)
        if source is None or target is None:
            return False
        if source.owner != attacker:
            return False

        defender = self.enemy_of(attacker)
        if target.owner != defender:
            return False

        attacker_remaining = self._clamp_troops_to_cell_cap(attacker_remaining, source_q, source_r)
        defender_remaining = self._clamp_troops_to_cell_cap(defender_remaining, target_q, target_r)

        source.troops[attacker] = attacker_remaining
        source.troops[defender] = 0

        target.troops[defender] = defender_remaining
        target.troops[attacker] = 0

        if defender_remaining == 0 and attacker_remaining > 0:
            source.troops[attacker] -= 1
            target.owner = attacker
            target.troops[attacker] = 1
            target.troops[defender] = 0
        else:
            target.owner = defender

        self._rebuild_boundary_edges()
        self.validate_integrity()
        return True

    def count_control(self):
        player_cells = 0
        cpu_cells = 0
        for cell in self.get_all_cells():
            if cell.owner == OWNER_PLAYER:
                player_cells += 1
            elif cell.owner == OWNER_CPU:
                cpu_cells += 1
        return player_cells, cpu_cells

    def capital_coord(self, owner):
        return self.capitals.get(owner)

    def town_coords(self, origin_owner=None):
        if origin_owner is None:
            coords = set()
            for owner in (OWNER_PLAYER, OWNER_CPU):
                coords.update(self.towns_by_origin.get(owner, set()))
            return coords
        return set(self.towns_by_origin.get(origin_owner, set()))

    def is_town_coord(self, q, r):
        return (q, r) in self.town_coords_set

    def is_capital_coord(self, q, r):
        coord = (q, r)
        return any(capital == coord for capital in self.capitals.values())

    def is_city_coord(self, q, r):
        return self.is_town_coord(q, r)

    def capital_owner_at(self, q, r):
        coord = (q, r)
        for owner, capital in self.capitals.items():
            if capital == coord:
                return owner
        return None

    def controlled_supplied_city_count(self, owner):
        count = 0
        for coord in self.town_coords_set:
            cell = self.get_cell(coord[0], coord[1])
            if cell is None or cell.owner != owner:
                continue
            if self.in_supply(coord[0], coord[1], owner):
                count += 1
        return count

    def deployment_bonus_chunks(self, owner):
        return self.controlled_supplied_city_count(owner) * DEPLOY_BONUS_CHUNKS_PER_SUPPLIED_TOWN

    def in_supply(self, q, r, owner):
        cell = self.get_cell(q, r)
        if cell is None or cell.owner != owner:
            return False
        return (q, r) in self._capital_supply_reach(owner)

    def _capital_supply_reach(self, owner):
        if owner in self._supply_reach_cache:
            return self._supply_reach_cache[owner]

        capital = self.capital_coord(owner)
        if capital is None:
            self._supply_reach_cache[owner] = set()
            return self._supply_reach_cache[owner]

        capital_cell = self.get_cell(capital[0], capital[1])
        if capital_cell is None or capital_cell.owner != owner:
            self._supply_reach_cache[owner] = set()
            return self._supply_reach_cache[owner]

        reachable = set()
        queue = deque([capital])
        reachable.add(capital)

        while queue:
            q, r = queue.popleft()
            for neighbor in self.get_neighbors(q, r):
                if neighbor.owner != owner:
                    continue
                coord = (neighbor.q, neighbor.r)
                if coord in reachable:
                    continue
                reachable.add(coord)
                queue.append(coord)

        self._supply_reach_cache[owner] = reachable
        return reachable

    def _generate_ownership_cut_by_row(self):
        target_p1_cells = (self.cols * self.rows) // 2
        p1_counts = [self.cols // 2 for _ in range(self.rows)]

        current = sum(p1_counts)
        while current < target_p1_cells:
            options = [i for i, value in enumerate(p1_counts) if value < self.cols - 1]
            if not options:
                break
            idx = random.choice(options)
            p1_counts[idx] += 1
            current += 1

        while current > target_p1_cells:
            options = [i for i, value in enumerate(p1_counts) if value > 1]
            if not options:
                break
            idx = random.choice(options)
            p1_counts[idx] -= 1
            current -= 1

        self._randomize_ownership_counts(p1_counts)

        if self.rows > 1 and len(set(p1_counts)) == 1 and self.cols > 2:
            if p1_counts[0] < self.cols - 1 and p1_counts[1] > 1:
                p1_counts[0] += 1
                p1_counts[1] -= 1
            elif p1_counts[0] > 1 and p1_counts[1] < self.cols - 1:
                p1_counts[0] -= 1
                p1_counts[1] += 1

        return [count - 1 for count in p1_counts]

    def _randomize_ownership_counts(self, p1_counts):
        if self.rows < 2:
            return

        iterations = max(12, self.rows * 8)
        for _ in range(iterations):
            row = random.randrange(self.rows - 1)
            if random.random() < 0.5:
                grow_idx, shrink_idx = row, row + 1
            else:
                grow_idx, shrink_idx = row + 1, row

            if p1_counts[grow_idx] >= self.cols - 1:
                continue
            if p1_counts[shrink_idx] <= 1:
                continue

            new_grow = p1_counts[grow_idx] + 1
            new_shrink = p1_counts[shrink_idx] - 1
            if not self._is_local_step_valid(p1_counts, grow_idx, new_grow):
                continue
            if not self._is_local_step_valid(p1_counts, shrink_idx, new_shrink):
                continue

            p1_counts[grow_idx] = new_grow
            p1_counts[shrink_idx] = new_shrink

    def _is_local_step_valid(self, counts, idx, candidate):
        max_step = 2
        if idx > 0 and abs(candidate - counts[idx - 1]) > max_step:
            return False
        if idx < self.rows - 1 and abs(candidate - counts[idx + 1]) > max_step:
            return False
        return True

    def _assign_side_ownership_from_cut(self):
        for r in range(self.rows):
            cut = self.ownership_cut_by_row[r]
            for q in range(self.cols):
                cell = self.get_cell(q, r)
                cell.owner = OWNER_PLAYER if q <= cut else OWNER_CPU
                cell.troops[OWNER_P1] = 0
                cell.troops[OWNER_P2] = 0

    def _assign_cities(self):
        capitals = {}
        towns_by_origin = {
            OWNER_PLAYER: set(),
            OWNER_CPU: set(),
        }
        town_coords_set = set()

        required = int(CITIES_PER_PLAYER)
        if required < 1:
            raise ValueError("CITIES_PER_PLAYER must be at least 1")

        for owner in (OWNER_PLAYER, OWNER_CPU):
            coords, frontline_distance = self._pick_city_coords_for_owner(owner, required)
            if len(coords) < required:
                raise ValueError(f"Unable to place required cities for owner {owner}")

            capital = max(coords, key=lambda coord: self._city_rank(coord, frontline_distance))
            capitals[owner] = capital
            for coord in coords:
                town_coords_set.add(coord)
                towns_by_origin[owner].add(coord)

        self.capitals = capitals
        self.towns_by_origin = towns_by_origin
        self.town_coords_set = town_coords_set
        self._supply_reach_cache = {}

    def _pick_city_coords_for_owner(self, owner, count):
        if count <= 0:
            return [], {}

        owner_cells = [c for c in self.get_all_cells() if c.owner == owner]
        if not owner_cells:
            return [], {}

        frontline_distance = self._frontline_distance_map(owner_cells, owner)
        min_depth = int(CITY_MIN_FRONTLINE_DISTANCE)

        plain_candidates = self._city_candidates(
            owner_cells,
            frontline_distance,
            min_depth,
            plain_only=True,
        )
        if len(plain_candidates) >= count:
            coords = self._select_spread_city_coords(plain_candidates, frontline_distance, count)
            if len(coords) == count:
                return coords, frontline_distance

        fallback_candidates = self._city_candidates(
            owner_cells,
            frontline_distance,
            min_depth,
            plain_only=False,
        )
        if len(fallback_candidates) >= count:
            coords = self._select_spread_city_coords(fallback_candidates, frontline_distance, count)
            if len(coords) == count:
                return coords, frontline_distance

        return [], frontline_distance

    def _frontline_distance_map(self, owner_cells, owner):
        frontline = {(c.q, c.r) for c in owner_cells if self.is_frontline_cell(c.q, c.r)}
        distance = {}

        if frontline:
            queue = deque(frontline)
            for coord in frontline:
                distance[coord] = 0

            while queue:
                q, r = queue.popleft()
                base_dist = distance[(q, r)]
                for neighbor in self.get_neighbors(q, r):
                    if neighbor.owner != owner:
                        continue
                    coord = (neighbor.q, neighbor.r)
                    if coord in distance:
                        continue
                    distance[coord] = base_dist + 1
                    queue.append(coord)
            return distance

        fallback_distance = self.cols + self.rows
        for cell in owner_cells:
            distance[(cell.q, cell.r)] = fallback_distance
        return distance

    def _city_rank(self, coord, frontline_distance):
        q, r = coord
        depth = frontline_distance.get(coord, 0)
        interior = 1 if len(self.get_neighbors(q, r)) == 6 else 0
        center_q = (self.cols - 1) / 2.0
        center_r = (self.rows - 1) / 2.0
        center_bias = -abs(q - center_q) - abs(r - center_r)
        return depth, interior, center_bias

    def _city_candidates(self, owner_cells, frontline_distance, min_depth, plain_only=True):
        ranked = []
        for cell in owner_cells:
            if plain_only and cell.terrain != TERRAIN_PLAIN:
                continue
            coord = (cell.q, cell.r)
            if frontline_distance.get(coord, 0) < min_depth:
                continue
            ranked.append((self._city_rank(coord, frontline_distance), coord))

        ranked.sort(reverse=True)
        return [coord for _, coord in ranked]

    def _select_spread_city_coords(self, candidates, frontline_distance, count):
        if len(candidates) < count:
            return []
        if len(candidates) == count:
            return list(candidates)

        best_combo = None
        best_score = None

        combo_limit = max(1, int(CITY_PLACEMENT_MAX_COMBINATIONS))
        for idx, combo in enumerate(combinations(candidates, count)):
            if idx >= combo_limit:
                break
            cluster_score = self._city_cluster_score(combo, frontline_distance)
            if best_combo is None or cluster_score > best_score:
                best_combo = combo
                best_score = cluster_score

        if best_combo is not None:
            return list(best_combo)
        return list(candidates[:count])

    def _city_cluster_metrics(self, coords):
        pair_distances = []
        for idx, coord in enumerate(coords):
            for other in coords[idx + 1:]:
                pair_distances.append(self._hex_distance(coord, other))

        if not pair_distances:
            return 0, 0

        min_pair = min(pair_distances)
        max_pair = max(pair_distances)
        spread_gap = max_pair - min_pair
        return min_pair, spread_gap

    def _city_cluster_score(self, coords, frontline_distance):
        min_pair, spread_gap = self._city_cluster_metrics(coords)
        total_depth = sum(frontline_distance.get(coord, 0) for coord in coords)
        return (
            1 if min_pair >= int(CITY_MIN_PAIR_DISTANCE) else 0,
            1 if spread_gap <= int(CITY_SPACING_MARGIN) else 0,
            min_pair,
            -spread_gap,
            total_depth,
        )

    def _is_player_owner(self, owner):
        return owner in (OWNER_PLAYER, OWNER_CPU)

    def _iter_frontline_edges(self):
        for cell in self.get_all_cells():
            if not self._is_player_owner(cell.owner):
                continue

            for neighbor in self.get_neighbors(cell.q, cell.r):
                if not self._is_player_owner(neighbor.owner):
                    continue
                if cell.owner == neighbor.owner:
                    continue

                a = (cell.q, cell.r)
                b = (neighbor.q, neighbor.r)
                if a < b:
                    yield (a, b)

    def _rebuild_boundary_edges(self):
        self.boundary_edges = set(self._iter_frontline_edges())
        self._encircled_cells_cache = None
        self._supply_reach_cache = {}

    def frontline_cells(self, player):
        cells = set()
        for a, b in self.boundary_edges:
            cell_a = self.get_cell(a[0], a[1])
            cell_b = self.get_cell(b[0], b[1])
            if cell_a is not None and cell_a.owner == player:
                cells.add(a)
            if cell_b is not None and cell_b.owner == player:
                cells.add(b)
        return [self.cells[q][r] for (q, r) in sorted(cells)]

    def has_river_between(self, q1, r1, q2, r2):
        edge = self._edge_key((q1, r1), (q2, r2))
        return edge in self.river_edges

    def is_frontline_cell(self, q, r):
        cell = self.get_cell(q, r)
        if cell is None or not self._is_player_owner(cell.owner):
            return False

        enemy = self.enemy_of(cell.owner)
        return any(neighbor.owner == enemy for neighbor in self.get_neighbors(q, r))

    def friendly_adjacent_count(self, q, r):
        cell = self.get_cell(q, r)
        if cell is None or not self.is_frontline_cell(q, r):
            return 0

        owner = cell.owner
        count = 0
        for neighbor in self.get_neighbors(q, r):
            if neighbor.owner == owner:
                count += 1
        return count

    def is_encircled_cell(self, q, r):
        cell = self.get_cell(q, r)
        if cell is None or not self._is_player_owner(cell.owner):
            return False
        return (q, r) in self._encircled_cells()

    def _encircled_cells(self):
        if self._encircled_cells_cache is not None:
            return self._encircled_cells_cache

        # A cell is encircled if it cannot trace a same-owner path to its own capital.
        # This reuses supply reach, which already computes owner-connected components from capital.
        encircled = set()
        for owner in (OWNER_PLAYER, OWNER_CPU):
            owner_supply = self._capital_supply_reach(owner)
            for cell in self.get_all_cells():
                if cell.owner != owner:
                    continue
                coord = (cell.q, cell.r)
                if coord not in owner_supply:
                    encircled.add(coord)

        self._encircled_cells_cache = encircled
        return encircled

    def frontline_topology(self, q, r):
        if self.is_encircled_cell(q, r):
            return "exposed"

        if not self.is_frontline_cell(q, r):
            return None

        if self.friendly_adjacent_count(q, r) >= 2:
            return "supported"
        return "exposed"

    def defense_topology_modifier(self, q, r):
        topology = self.frontline_topology(q, r)
        if topology == "exposed":
            return -COMBAT_EXPOSED_DEFENDER_ATTACKER_DELTA
        return 0

    def validate_integrity(self):
        for cell in self.get_all_cells():
            if cell.owner not in (OWNER_PLAYER, OWNER_CPU, OWNER_NEUTRAL):
                raise ValueError(f"Invalid owner at ({cell.q},{cell.r}): {cell.owner}")

            player_troops = cell.troops[OWNER_PLAYER]
            cpu_troops = cell.troops[OWNER_CPU]
            if player_troops < 0 or cpu_troops < 0:
                raise ValueError(
                    f"Negative troops at ({cell.q},{cell.r}): "
                    f"player={player_troops}, cpu={cpu_troops}"
                )
            cap = self._cell_troop_cap(cell.q, cell.r)
            if player_troops > cap or cpu_troops > cap:
                raise ValueError(
                    f"Per-side cap exceeded at ({cell.q},{cell.r}): "
                    f"cap={cap} player={player_troops}, cpu={cpu_troops}"
                )
            if player_troops + cpu_troops > cap:
                raise ValueError(
                    f"Cell cap exceeded at ({cell.q},{cell.r}): "
                    f"cap={cap} total={player_troops + cpu_troops}"
                )

            if cell.owner == OWNER_PLAYER and cpu_troops != 0:
                raise ValueError(f"Enemy troops on Player cell ({cell.q},{cell.r}): cpu={cpu_troops}")
            if cell.owner == OWNER_CPU and player_troops != 0:
                raise ValueError(
                    f"Enemy troops on CPU cell ({cell.q},{cell.r}): player={player_troops}"
                )
            if cell.owner == OWNER_NEUTRAL and (player_troops != 0 or cpu_troops != 0):
                raise ValueError(f"Troops on neutral cell ({cell.q},{cell.r})")

        for (a, b) in self.boundary_edges:
            c1 = self.get_cell(a[0], a[1])
            c2 = self.get_cell(b[0], b[1])
            if c1 is None or c2 is None:
                raise ValueError("Boundary edge references invalid cell")
            if not self.are_adjacent(c1.q, c1.r, c2.q, c2.r):
                raise ValueError("Boundary edge references non-adjacent cells")
            if c1.owner == c2.owner:
                raise ValueError("Boundary edge references same-owner cells")

        expected_frontline = set(self._iter_frontline_edges())
        if self.boundary_edges != expected_frontline:
            raise ValueError("Boundary edges out of sync with enemy-adjacent cells")

        for (a, b) in self.river_edges:
            c1 = self.get_cell(a[0], a[1])
            c2 = self.get_cell(b[0], b[1])
            if c1 is None or c2 is None:
                raise ValueError("River edge references invalid cell")
            if not self.are_adjacent(c1.q, c1.r, c2.q, c2.r):
                raise ValueError("River edge references non-adjacent cells")

        for owner in (OWNER_PLAYER, OWNER_CPU):
            coord = self.capitals.get(owner)
            if coord is None:
                raise ValueError(f"Missing capital for owner {owner}")
            if self.get_cell(coord[0], coord[1]) is None:
                raise ValueError(f"Capital references invalid cell: owner={owner} coord={coord}")
            if self.get_cell(coord[0], coord[1]).terrain != TERRAIN_PLAIN:
                raise ValueError(f"Capital must be on plain terrain: owner={owner} coord={coord}")

            towns = self.towns_by_origin.get(owner, set())
            expected_towns = int(CITIES_PER_PLAYER)
            if len(towns) != expected_towns:
                raise ValueError(
                    f"Unexpected settlement count for owner {owner}: {len(towns)}"
                )
            if coord not in towns:
                raise ValueError(f"Capital must be included in towns: owner={owner} coord={coord}")
            for town in towns:
                town_cell = self.get_cell(town[0], town[1])
                if town_cell is None:
                    raise ValueError(f"Town references invalid cell: owner={owner} coord={town}")
                if town_cell.terrain != TERRAIN_PLAIN:
                    raise ValueError(f"Town must be on plain terrain: owner={owner} coord={town}")

        if len(self.town_coords_set) != int(CITIES_PER_PLAYER) * 2:
            raise ValueError("Settlement coordinate set size mismatch")

    def _generate_terrain(self):
        self._reset_terrain_to_plain()
        config = self._validate_spawn_configuration()
        self._generate_rivers(config["rivers"])
        self._generate_clustered_terrain(TERRAIN_MOUNTAIN, config["mountains"])
        self._generate_clustered_terrain(TERRAIN_FOREST, config["forests"])

    def _reset_terrain_to_plain(self):
        for cell in self.get_all_cells():
            cell.terrain = TERRAIN_PLAIN

    def _validate_spawn_configuration(self):
        rivers = normalize_range_config(MIN_RIVERS, MAX_RIVERS, "rivers")
        mountains = normalize_cluster_config(
            MIN_MOUNTAIN_CLUSTERS,
            MAX_MOUNTAIN_CLUSTERS,
            MAX_MOUNTAINS_PER_CLUSTER,
            "mountains",
        )
        forests = normalize_cluster_config(
            MIN_FOREST_CLUSTERS,
            MAX_FOREST_CLUSTERS,
            MAX_FORESTS_PER_CLUSTER,
            "forests",
        )

        blocked_for_terrain = len(self.town_coords_set)
        terrain_capacity = self.cols * self.rows - blocked_for_terrain
        if terrain_capacity < 0:
            raise ValueError("Settlement count exceeds board capacity")

        min_terrain_tiles = mountains[0] + forests[0]
        if min_terrain_tiles > terrain_capacity:
            raise ValueError(
                f"minimum terrain tiles ({min_terrain_tiles}) exceed available cells ({terrain_capacity})"
            )

        all_coords = self._all_coords()
        max_unique_river_edges = len(
            collect_adjacency_edges(
                all_coords,
                self._neighbor_coords,
            )
        )
        if rivers[0] > max_unique_river_edges:
            raise ValueError(
                f"minimum rivers ({rivers[0]}) exceed possible river edges ({max_unique_river_edges})"
            )

        if rivers[0] > 0 and len(collect_boundary_coords(all_coords, self._neighbor_coords)) < 2:
            raise ValueError("board has insufficient boundary cells to place rivers")

        return {
            "rivers": rivers,
            "mountains": mountains,
            "forests": forests,
        }

    def _generate_rivers(self, river_config):
        self.river_edges = set()
        min_rivers, max_rivers = river_config
        if max_rivers <= 0:
            return

        target_min_length = max(1, min(self.cols, self.rows) - 1)
        self.river_edges = generate_boundary_crossing_edges(
            coords=self._all_coords(),
            neighbor_coords_fn=self._neighbor_coords,
            coord_to_pixel_fn=self.axial_to_pixel,
            hex_radius=self.hex_radius,
            min_paths=min_rivers,
            max_paths=max_rivers,
            min_path_length=target_min_length,
            existing_edges=self.river_edges,
        )

    def _path_edges(self, coord_path):
        if not coord_path or len(coord_path) < 2:
            return []
        edges = []
        for idx in range(len(coord_path) - 1):
            edges.append(self._edge_key(coord_path[idx], coord_path[idx + 1]))
        return edges

    def _all_adjacency_edges(self):
        return collect_adjacency_edges(
            self._all_coords(),
            self._neighbor_coords,
        )

    def _boundary_cell_coords(self):
        return collect_boundary_coords(
            self._all_coords(),
            self._neighbor_coords,
        )

    def _generate_clustered_terrain(self, terrain_type, cluster_config):
        min_clusters, max_clusters, max_tiles_per_cluster = cluster_config
        if max_clusters <= 0:
            return

        clusters = generate_clustered_regions(
            available_coords=self._available_terrain_coords(),
            neighbor_coords_fn=self._neighbor_coords,
            min_clusters=min_clusters,
            max_clusters=max_clusters,
            max_tiles_per_cluster=max_tiles_per_cluster,
            is_interior_fn=self._is_interior_coord,
        )
        for cluster_coords in clusters:
            for coord in cluster_coords:
                cell = self.get_cell(coord[0], coord[1])
                if cell is not None:
                    cell.terrain = terrain_type

    def _available_terrain_coords(self):
        blocked = self.town_coords_set
        return {
            (cell.q, cell.r)
            for cell in self.get_all_cells()
            if cell.terrain == TERRAIN_PLAIN and (cell.q, cell.r) not in blocked
        }

    def _all_coords(self):
        return [(cell.q, cell.r) for cell in self.get_all_cells()]

    def _is_interior_coord(self, coord):
        return len(self._neighbor_coords(coord)) == 6

    def _neighbor_coords(self, coord):
        q, r = coord
        return [(neighbor.q, neighbor.r) for neighbor in self.get_neighbors(q, r)]


