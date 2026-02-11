import math
import random
from constants import *


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

        self._assign_side_ownership_from_cut()
        self._rebuild_boundary_edges()
        self._generate_terrain()
        self.validate_integrity()

    @staticmethod
    def compute_bottom_bar_height():
        return BB_HEIGHT

    @staticmethod
    def _board_width(cols, radius):
        return radius * (1.5 * (cols - 1) + 2)

    @staticmethod
    def _board_height(cols, rows, radius):
        odd_offset = 0.5 if cols > 1 else 0.0
        return radius * ((rows - 1 + odd_offset) * math.sqrt(3) + 2)

    @staticmethod
    def compute_grid_size():
        bar_height = HexGrid.compute_bottom_bar_height()
        available_width = SCREEN_WIDTH
        available_height = SCREEN_HEIGHT - bar_height
        target_tiles = max(2, int(GRID_HEX_COUNT))
        if target_tiles % 2 != 0:
            target_tiles -= 1

        best = None
        best_score = None
        target_aspect = available_width / max(1, available_height)

        max_cols = max(2, int(math.sqrt(target_tiles * target_aspect) * 2) + 6)
        max_rows = max(1, int(math.sqrt(target_tiles / max(target_aspect, 0.1)) * 2) + 6)

        for cols in range(2, max_cols + 1):
            for rows in range(1, max_rows + 1):
                area = cols * rows
                if area % 2 != 0:
                    continue

                radius_by_width = available_width / (1.5 * (cols - 1) + 2)
                odd_offset = 0.5 if cols > 1 else 0.0
                radius_by_height = available_height / (((rows - 1 + odd_offset) * math.sqrt(3)) + 2)
                radius = int(min(radius_by_width, radius_by_height))
                if radius < 6:
                    continue

                # Primary objective: match requested tile count as closely as possible.
                # Secondary objective: use the largest hex radius that fits.
                # Third objective: keep board aspect close to screen aspect.
                diff_tiles = abs(area - target_tiles)
                diff_aspect = abs((cols / rows) - target_aspect)
                score = (diff_tiles, -radius, diff_aspect, -area)

                if best is None or score < best_score:
                    best = (cols, rows, radius)
                    best_score = score

        if best is not None:
            cols, rows, radius = best
            board_width = HexGrid._board_width(cols, radius)
            board_height = HexGrid._board_height(cols, rows, radius)
            origin_x = int((available_width - board_width) / 2)
            origin_y = int((available_height - board_height) / 2)
            return cols, rows, radius, origin_x, origin_y, bar_height

        # Safe fallback (should not normally happen).
        cols, rows, radius = 2, 1, 20
        board_width = HexGrid._board_width(cols, radius)
        board_height = HexGrid._board_height(cols, rows, radius)
        origin_x = int((available_width - board_width) / 2)
        origin_y = int((available_height - board_height) / 2)
        return cols, rows, radius, origin_x, origin_y, bar_height

    @staticmethod
    def enemy_of(player):
        return OWNER_P2 if player == OWNER_P1 else OWNER_P1

    def axial_to_pixel(self, q, r):
        radius = self.hex_radius
        x = self.board_origin_x + radius * (1.5 * q + 1)
        if q % 2 == 0:
            y = self.board_origin_y + radius + r * (math.sqrt(3) * radius)
        else:
            y = self.board_origin_y + radius + (r + 0.5) * (math.sqrt(3) * radius)
        return x, y

    def get_cell(self, q, r):
        if 0 <= q < self.cols and 0 <= r < self.rows:
            return self.cells[q][r]
        return None

    def get_all_cells(self):
        return [cell for col in self.cells for cell in col]

    def get_neighbors(self, q, r):
        if q % 2 == 0:
            deltas = [(1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (0, 1)]
        else:
            deltas = [(1, 1), (1, 0), (0, -1), (-1, 0), (-1, 1), (0, 1)]

        neighbors = []
        for dq, dr in deltas:
            cell = self.get_cell(q + dq, r + dr)
            if cell is not None:
                neighbors.append(cell)
        return neighbors

    def are_adjacent(self, q1, r1, q2, r2):
        return any(n.q == q2 and n.r == r2 for n in self.get_neighbors(q1, r1))

    def add_troop(self, q, r, player):
        cell = self.get_cell(q, r)
        if cell is None:
            return False
        if cell.owner != player:
            return False
        if cell.total_troops() >= MAX_TROOPS_PER_CELL:
            return False
        enemy = self.enemy_of(player)
        if cell.troops[enemy] > 0:
            return False

        cell.troops[player] += 1
        self.validate_integrity()
        return True

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
        if target.total_troops() >= MAX_TROOPS_PER_CELL:
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

        attacker_remaining = max(0, min(MAX_TROOPS_PER_CELL, int(attacker_remaining)))
        defender_remaining = max(0, min(MAX_TROOPS_PER_CELL, int(defender_remaining)))

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
        p1 = 0
        p2 = 0
        for cell in self.get_all_cells():
            if cell.owner == OWNER_P1:
                p1 += 1
            elif cell.owner == OWNER_P2:
                p2 += 1
        return p1, p2

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
                cell.owner = OWNER_P1 if q <= cut else OWNER_P2
                cell.troops[OWNER_P1] = 0
                cell.troops[OWNER_P2] = 0

    def _rebuild_boundary_edges(self):
        edges = set()
        for cell in self.get_all_cells():
            for neighbor in self.get_neighbors(cell.q, cell.r):
                if cell.owner == neighbor.owner:
                    continue
                a = (cell.q, cell.r)
                b = (neighbor.q, neighbor.r)
                edges.add((a, b) if a < b else (b, a))
        self.boundary_edges = edges

    def validate_integrity(self):
        for cell in self.get_all_cells():
            if cell.owner not in (OWNER_P1, OWNER_P2, OWNER_NEUTRAL):
                raise ValueError(f"Invalid owner at ({cell.q},{cell.r}): {cell.owner}")

            p1 = cell.troops[OWNER_P1]
            p2 = cell.troops[OWNER_P2]
            if p1 < 0 or p2 < 0:
                raise ValueError(f"Negative troops at ({cell.q},{cell.r}): p1={p1}, p2={p2}")
            if p1 > MAX_TROOPS_PER_CELL or p2 > MAX_TROOPS_PER_CELL:
                raise ValueError(f"Per-side max exceeded at ({cell.q},{cell.r}): p1={p1}, p2={p2}")
            if p1 + p2 > MAX_TROOPS_PER_CELL:
                raise ValueError(f"Cell max exceeded at ({cell.q},{cell.r}): total={p1+p2}")

            if cell.owner == OWNER_P1 and p2 != 0:
                raise ValueError(f"Enemy troops on P1 cell ({cell.q},{cell.r}): p2={p2}")
            if cell.owner == OWNER_P2 and p1 != 0:
                raise ValueError(f"Enemy troops on P2 cell ({cell.q},{cell.r}): p1={p1}")
            if cell.owner == OWNER_NEUTRAL and (p1 != 0 or p2 != 0):
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

    def _generate_terrain(self):
        self._generate_rivers()
        self._generate_mountains()

    def _generate_rivers(self):
        min_rivers = max(0, int(MIN_RIVERS))
        max_rivers = max(min_rivers, int(MAX_RIVERS))
        river_count = random.randint(min_rivers, max_rivers)
        attempts = 0
        created = 0

        while created < river_count and attempts < max(8, river_count * 10):
            attempts += 1
            path = self._build_edge_to_edge_river()
            if not path:
                continue
            for q, r in path:
                self.cells[q][r].terrain = TERRAIN_RIVER
            created += 1

    def _build_edge_to_edge_river(self):
        def is_valid_river_cell(q, r):
            return self.get_cell(q, r) is not None and self.cells[q][r].terrain != TERRAIN_RIVER

        # Build a one-cell-thick edge-to-edge line that always advances on one main axis.
        # This keeps a meandering shape but prevents local triangular river blobs.
        def build_left_right():
            for _ in range(24):
                q = 0
                r = random.randint(0, self.rows - 1)
                if not is_valid_river_cell(q, r):
                    continue

                path = [(q, r)]
                turned = False

                while q < self.cols - 1:
                    forward = [
                        n for n in self.get_neighbors(q, r)
                        if n.q == q + 1 and is_valid_river_cell(n.q, n.r)
                    ]
                    if not forward:
                        break
                    chosen = random.choice(forward)
                    if chosen.r != r:
                        turned = True
                    q, r = chosen.q, chosen.r
                    path.append((q, r))

                if q == self.cols - 1 and (turned or self.cols <= 2):
                    return path
            return None

        def build_top_bottom():
            for _ in range(24):
                q = random.randint(0, self.cols - 1)
                r = 0
                if not is_valid_river_cell(q, r):
                    continue

                path = [(q, r)]
                turned = False

                while r < self.rows - 1:
                    forward = [
                        n for n in self.get_neighbors(q, r)
                        if n.r == r + 1 and is_valid_river_cell(n.q, n.r)
                    ]
                    if not forward:
                        break
                    chosen = random.choice(forward)
                    if chosen.q != q:
                        turned = True
                    q, r = chosen.q, chosen.r
                    path.append((q, r))

                if r == self.rows - 1 and (turned or self.rows <= 2):
                    return path
            return None

        if random.choice(["left_right", "top_bottom"]) == "left_right":
            path = build_left_right()
            if path:
                return path
            return build_top_bottom()

        path = build_top_bottom()
        if path:
            return path
        return build_left_right()

    def _generate_mountains(self):
        min_clusters = max(0, int(MIN_MOUNTAIN_CLUSTERS))
        max_clusters = max(min_clusters, int(MAX_MOUNTAIN_CLUSTERS))
        cluster_count = random.randint(min_clusters, max_clusters)
        candidates = [c for c in self.get_all_cells() if c.terrain == TERRAIN_PLAIN]
        random.shuffle(candidates)

        created = 0
        for seed in candidates:
            if created >= cluster_count:
                break
            if seed.terrain != TERRAIN_PLAIN:
                continue
            cluster_size = random.randint(1, MAX_MOUNTAINS_PER_CLUSTER)
            self._grow_mountain_cluster(seed, cluster_size)
            created += 1

    def _grow_mountain_cluster(self, seed, target_size):
        frontier = [seed]
        placed = 0

        while frontier and placed < target_size:
            cell = frontier.pop(random.randrange(len(frontier)))
            if cell.terrain != TERRAIN_PLAIN:
                continue

            cell.terrain = TERRAIN_MOUNTAIN
            placed += 1

            neighbors = self.get_neighbors(cell.q, cell.r)
            random.shuffle(neighbors)
            for neighbor in neighbors:
                if neighbor.terrain == TERRAIN_PLAIN:
                    frontier.append(neighbor)
