import math
import random
from constants import *

class HexCell:
    def __init__(self, q, r):
        self.q = q
        self.r = r
        self.owner = OWNER_NEUTRAL
        self.frontline = False
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
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.cells = [[HexCell(q, r) for r in range(rows)] for q in range(cols)]
        self.frontline_q_by_row = []
        self._init_frontline()
        self._assign_side_ownership()
        self._generate_terrain()

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

    def get_cell(self, q, r):
        if 0 <= q < self.cols and 0 <= r < self.rows:
            return self.cells[q][r]
        return None

    def get_neighbors(self, q, r):
        if q % 2 == 0:
            deltas = [(1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (0, 1)]
        else:
            deltas = [(1, 1), (1, 0), (0, -1), (-1, 0), (-1, 1), (0, 1)]
        result = []
        for dq, dr in deltas:
            nq, nr = q + dq, r + dr
            cell = self.get_cell(nq, nr)
            if cell is not None:
                result.append(cell)
        return result

    def are_adjacent(self, q1, r1, q2, r2):
        return any(n.q == q2 and n.r == r2 for n in self.get_neighbors(q1, r1))

    def add_troop(self, q, r, player):
        cell = self.get_cell(q, r)
        if cell is None:
            return False
        if cell.total_troops() >= MAX_TROOPS_PER_CELL:
            return False
        if cell.troops_of(player) == 0 and cell.total_troops() > 0:
            return False
        cell.troops[player] += 1
        if not cell.frontline:
            cell.owner = player
        return True

    def remove_troop(self, q, r, player):
        cell = self.get_cell(q, r)
        if cell is None:
            return False
        if cell.troops[player] <= 0:
            return False
        cell.troops[player] -= 1
        if cell.total_troops() == 0 and not cell.frontline:
            cell.owner = OWNER_NEUTRAL
        return True

    def count_control(self):
        p1 = p2 = 0
        for q in range(self.cols):
            for r in range(self.rows):
                owner = self.cells[q][r].owner
                if owner == OWNER_P1:
                    p1 += 1
                elif owner == OWNER_P2:
                    p2 += 1
        return p1, p2

    def get_all_cells(self):
        return [cell for row in self.cells for cell in row]

    def _init_frontline(self):
        base_q = self.cols // 2
        for r in range(self.rows):
            self.frontline_q_by_row.append(base_q)
            cell = self.cells[base_q][r]
            cell.frontline = True
            cell.owner = OWNER_NEUTRAL
            cell.troops[OWNER_P1] = 0
            cell.troops[OWNER_P2] = 0

    def _assign_side_ownership(self):
        for r in range(self.rows):
            f_q = self.frontline_q_by_row[r]
            for q in range(self.cols):
                cell = self.cells[q][r]
                if cell.frontline:
                    cell.owner = OWNER_NEUTRAL
                    continue
                if q < f_q:
                    cell.owner = OWNER_P1
                elif q > f_q:
                    cell.owner = OWNER_P2

    def _generate_terrain(self):
        self._generate_rivers()
        self._generate_mountains()

    def _generate_rivers(self):
        river_count = random.randint(0, MAX_RIVERS)
        attempts = 0
        created = 0

        while created < river_count and attempts < river_count * 8:
            attempts += 1
            path = self._build_edge_to_edge_river()
            if not path:
                continue
            for q, r in path:
                self.cells[q][r].terrain = TERRAIN_RIVER
            created += 1

    def _build_edge_to_edge_river(self):
        orientation = random.choice(["left_right", "top_bottom"])
        if orientation == "left_right":
            start = (0, random.randint(0, self.rows - 1))
            end = (self.cols - 1, random.randint(0, self.rows - 1))
        else:
            start = (random.randint(0, self.cols - 1), 0)
            end = (random.randint(0, self.cols - 1), self.rows - 1)

        q, r = start
        path = [(q, r)]
        visited = {start}
        max_steps = self.cols * self.rows

        for _ in range(max_steps):
            if (q, r) == end:
                return path

            neighbors = self.get_neighbors(q, r)
            if not neighbors:
                return None

            def score(cell):
                manhattan = abs(cell.q - end[0]) + abs(cell.r - end[1])
                reuse_penalty = 2 if cell.terrain == TERRAIN_RIVER else 0
                return manhattan + reuse_penalty

            neighbors.sort(key=score)

            # Mostly move toward the target, with occasional drift.
            pick_pool = neighbors[: min(3, len(neighbors))]
            nxt = random.choice(pick_pool if random.random() < 0.25 else [pick_pool[0]])

            q, r = nxt.q, nxt.r
            if (q, r) in visited:
                continue
            visited.add((q, r))
            path.append((q, r))

        return None

    def _generate_mountains(self):
        cluster_count = random.randint(0, MAX_MOUNTAIN_CLUSTERS)
        candidates = [c for c in self.get_all_cells() if c.terrain == TERRAIN_PLAIN and not c.frontline]
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
            if cell.terrain != TERRAIN_PLAIN or cell.frontline:
                continue

            cell.terrain = TERRAIN_MOUNTAIN
            placed += 1

            neighbors = self.get_neighbors(cell.q, cell.r)
            random.shuffle(neighbors)
            for n in neighbors:
                if n.terrain == TERRAIN_PLAIN and not n.frontline:
                    frontier.append(n)

    def shift_frontline_row(self, r, direction):
        old_q = self.frontline_q_by_row[r]
        new_q = old_q + direction
        if new_q <= 0 or new_q >= self.cols - 1:
            return False

        old_front = self.get_cell(old_q, r)
        new_front = self.get_cell(new_q, r)

        winner = OWNER_P1 if direction > 0 else OWNER_P2
        loser = OWNER_P2 if winner == OWNER_P1 else OWNER_P1

        old_front.frontline = False
        old_front.owner = winner if old_front.total_troops() > 0 else winner
        old_front.troops[loser] = 0

        new_front.frontline = True
        new_front.owner = OWNER_NEUTRAL
        new_front.troops[OWNER_P1] = 0
        new_front.troops[OWNER_P2] = 0

        self.frontline_q_by_row[r] = new_q
        self._realign_row_ownership(r)
        return True

    def _realign_row_ownership(self, r):
        f_q = self.frontline_q_by_row[r]
        for q in range(self.cols):
            cell = self.get_cell(q, r)
            if cell.frontline:
                cell.owner = OWNER_NEUTRAL
                cell.troops[OWNER_P1] = 0
                cell.troops[OWNER_P2] = 0
                continue

            expected = OWNER_P1 if q < f_q else OWNER_P2
            cell.owner = expected

            enemy = OWNER_P2 if expected == OWNER_P1 else OWNER_P1
            cell.troops[enemy] = 0
