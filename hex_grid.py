import math
import random
import heapq
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
        # River representation: edges between adjacent cells.
        self.river_edges = set()
        # Cached coordinates of cells in fully encircled owner groups.
        self._encircled_cells_cache = None

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
        return OWNER_CPU if player == OWNER_PLAYER else OWNER_PLAYER

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
        if cell.total_troops() + count > MAX_TROOPS_PER_CELL:
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

        # "On or behind the frontline" maps to all friendly cells in this ownership model.
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
        attack_dice = min(3, source.troops[attacker])
        if self.has_river_between(source_q, source_r, target_q, target_r):
            attack_dice -= 1
        if attack_dice <= 0:
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
        player_cells = 0
        cpu_cells = 0
        for cell in self.get_all_cells():
            if cell.owner == OWNER_PLAYER:
                player_cells += 1
            elif cell.owner == OWNER_CPU:
                cpu_cells += 1
        return player_cells, cpu_cells

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

        encircled = set()
        visited = set()
        for cell in self.get_all_cells():
            start = (cell.q, cell.r)
            if start in visited or not self._is_player_owner(cell.owner):
                continue

            owner = cell.owner
            enemy = self.enemy_of(owner)
            group = set()
            stack = [start]
            visited.add(start)
            surrounded = True

            while stack:
                q, r = stack.pop()
                group.add((q, r))
                neighbors = self.get_neighbors(q, r)

                # Border contact means the group is not fully enclosed by enemies.
                if len(neighbors) < 6:
                    surrounded = False

                for neighbor in neighbors:
                    coord = (neighbor.q, neighbor.r)
                    if neighbor.owner == owner:
                        if coord not in visited:
                            visited.add(coord)
                            stack.append(coord)
                    elif neighbor.owner != enemy:
                        surrounded = False

            if surrounded:
                encircled.update(group)

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
        if topology == "supported":
            return 1
        if topology == "exposed":
            return -1
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
            if player_troops > MAX_TROOPS_PER_CELL or cpu_troops > MAX_TROOPS_PER_CELL:
                raise ValueError(
                    f"Per-side max exceeded at ({cell.q},{cell.r}): "
                    f"player={player_troops}, cpu={cpu_troops}"
                )
            if player_troops + cpu_troops > MAX_TROOPS_PER_CELL:
                raise ValueError(
                    f"Cell max exceeded at ({cell.q},{cell.r}): "
                    f"total={player_troops + cpu_troops}"
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

    def _generate_terrain(self):
        self._generate_rivers()
        self._generate_forests()
        self._generate_mountains()

    def _generate_rivers(self):
        self.river_edges = set()
        min_rivers = max(0, int(MIN_RIVERS))
        max_rivers = max(min_rivers, int(MAX_RIVERS))
        river_count = random.randint(min_rivers, max_rivers)
        if river_count <= 0:
            return

        river_graph = self._build_river_graph()
        if river_graph is None:
            return

        target_min_length = max(1, min(self.cols, self.rows) - 1)
        attempts = 0
        created = 0

        while created < river_count and attempts < max(12, river_count * 24):
            attempts += 1
            path_edges = self._build_edge_to_edge_river(
                river_graph,
                min_length=target_min_length,
            )
            if not path_edges:
                continue
            self.river_edges.update(path_edges)
            created += 1

    @staticmethod
    def _vertex_key(x, y):
        scale = 1000
        return (int(round(x * scale)), int(round(y * scale)))

    @staticmethod
    def _vertex_distance_sq(a, b):
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        return dx * dx + dy * dy

    def _cell_vertex_keys(self, q, r):
        x, y = self.axial_to_pixel(q, r)
        vertices = []
        for i in range(6):
            angle = math.radians(60 * i)
            vx = x + self.hex_radius * math.cos(angle)
            vy = y + self.hex_radius * math.sin(angle)
            vertices.append(self._vertex_key(vx, vy))
        return tuple(vertices)

    def _build_river_graph(self):
        cell_vertices = {}
        side_counts = {}

        for cell in self.get_all_cells():
            coord = (cell.q, cell.r)
            vertices = self._cell_vertex_keys(cell.q, cell.r)
            cell_vertices[coord] = vertices
            for i in range(6):
                side = self._edge_key(vertices[i], vertices[(i + 1) % 6])
                side_counts[side] = side_counts.get(side, 0) + 1

        boundary_vertices = set()
        for side, count in side_counts.items():
            if count == 1:
                boundary_vertices.update(side)
        if not boundary_vertices:
            return None

        edge_vertices = {}
        vertex_graph = {}
        for cell in self.get_all_cells():
            a = (cell.q, cell.r)
            shared_candidates = set(cell_vertices[a])
            for neighbor in self.get_neighbors(cell.q, cell.r):
                b = (neighbor.q, neighbor.r)
                edge = self._edge_key(a, b)
                if edge in edge_vertices:
                    continue
                shared_vertices = tuple(sorted(shared_candidates.intersection(cell_vertices[b])))
                if len(shared_vertices) != 2:
                    continue
                v1, v2 = shared_vertices
                edge_vertices[edge] = (v1, v2)
                vertex_graph.setdefault(v1, []).append((v2, edge))
                vertex_graph.setdefault(v2, []).append((v1, edge))
        if not edge_vertices:
            return None

        reachable_boundary_vertices = [
            vertex for vertex in boundary_vertices if vertex in vertex_graph
        ]
        if len(reachable_boundary_vertices) < 2:
            return None

        xs = [vertex[0] for vertex in reachable_boundary_vertices]
        ys = [vertex[1] for vertex in reachable_boundary_vertices]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        tolerance = max(1, int(round(self.hex_radius * 300)))

        side_vertices = {"left": [], "right": [], "top": [], "bottom": []}
        for vertex in reachable_boundary_vertices:
            x, y = vertex
            if abs(x - min_x) <= tolerance:
                side_vertices["left"].append(vertex)
            if abs(x - max_x) <= tolerance:
                side_vertices["right"].append(vertex)
            if abs(y - min_y) <= tolerance:
                side_vertices["top"].append(vertex)
            if abs(y - max_y) <= tolerance:
                side_vertices["bottom"].append(vertex)

        return {
            "vertex_graph": vertex_graph,
            "boundary_vertices": tuple(reachable_boundary_vertices),
            "side_vertices": side_vertices,
        }

    def _pick_boundary_endpoints(self, side_vertices, boundary_vertices):
        axis_pairs = [("left", "right"), ("top", "bottom")]
        random.shuffle(axis_pairs)

        for side_a, side_b in axis_pairs:
            start_pool = side_vertices.get(side_a, [])
            end_pool = side_vertices.get(side_b, [])
            if not start_pool or not end_pool:
                continue
            start = random.choice(start_pool)
            ranked = sorted(
                end_pool,
                key=lambda v: self._vertex_distance_sq(start, v),
                reverse=True,
            )
            candidate_count = min(8, len(ranked))
            end = random.choice(ranked[:candidate_count])
            if start != end:
                return start, end

        all_boundary_vertices = list(boundary_vertices)
        if len(all_boundary_vertices) < 2:
            return None
        start = random.choice(all_boundary_vertices)
        ranked = sorted(
            all_boundary_vertices,
            key=lambda v: self._vertex_distance_sq(start, v),
            reverse=True,
        )
        for end in ranked:
            if start != end:
                return start, end
        return None

    def _find_vertex_path(self, start_vertex, end_vertex, vertex_graph):
        if start_vertex == end_vertex:
            return None

        frontier = [(0.0, start_vertex)]
        best_cost = {start_vertex: 0.0}
        previous = {}

        while frontier:
            cost, vertex = heapq.heappop(frontier)
            if cost > best_cost.get(vertex, float("inf")):
                continue
            if vertex == end_vertex:
                break

            for neighbor, edge in vertex_graph.get(vertex, []):
                step_cost = 1.0 + random.random() * 0.35
                if edge in self.river_edges:
                    step_cost += 2.5
                next_cost = cost + step_cost
                if next_cost >= best_cost.get(neighbor, float("inf")):
                    continue
                best_cost[neighbor] = next_cost
                previous[neighbor] = (vertex, edge)
                heapq.heappush(frontier, (next_cost, neighbor))

        if end_vertex not in previous:
            return None

        path_edges = []
        cursor = end_vertex
        while cursor != start_vertex:
            prev = previous.get(cursor)
            if prev is None:
                return None
            prev_vertex, edge = prev
            path_edges.append(edge)
            cursor = prev_vertex
        path_edges.reverse()
        return path_edges

    def _build_edge_to_edge_river(self, river_graph, min_length):
        vertex_graph = river_graph["vertex_graph"]
        boundary_vertices = river_graph["boundary_vertices"]
        side_vertices = river_graph["side_vertices"]

        for _ in range(28):
            endpoints = self._pick_boundary_endpoints(side_vertices, boundary_vertices)
            if endpoints is None:
                return None
            start_vertex, end_vertex = endpoints
            path_edges = self._find_vertex_path(start_vertex, end_vertex, vertex_graph)
            if not path_edges:
                continue
            if len(path_edges) < min_length:
                continue
            if not any(edge not in self.river_edges for edge in path_edges):
                continue
            return path_edges

        for _ in range(12):
            endpoints = self._pick_boundary_endpoints(side_vertices, boundary_vertices)
            if endpoints is None:
                return None
            start_vertex, end_vertex = endpoints
            path_edges = self._find_vertex_path(start_vertex, end_vertex, vertex_graph)
            if not path_edges:
                continue
            if any(edge not in self.river_edges for edge in path_edges):
                return path_edges
        return None

    def _generate_mountains(self):
        self._generate_clustered_terrain(
            MIN_MOUNTAIN_CLUSTERS,
            MAX_MOUNTAIN_CLUSTERS,
            MAX_MOUNTAINS_PER_CLUSTER,
            TERRAIN_MOUNTAIN,
        )

    def _generate_forests(self):
        self._generate_clustered_terrain(
            MIN_FOREST_CLUSTERS,
            MAX_FOREST_CLUSTERS,
            MAX_FORESTS_PER_CLUSTER,
            TERRAIN_FOREST,
        )

    def _generate_clustered_terrain(
        self,
        min_clusters,
        max_clusters,
        max_tiles_per_cluster,
        terrain_type,
    ):
        min_clusters = max(0, int(min_clusters))
        max_clusters = max(min_clusters, int(max_clusters))
        cluster_count = random.randint(min_clusters, max_clusters)
        candidates = [c for c in self.get_all_cells() if c.terrain == TERRAIN_PLAIN]
        random.shuffle(candidates)

        created = 0
        for seed in candidates:
            if created >= cluster_count:
                break
            if seed.terrain != TERRAIN_PLAIN:
                continue
            cluster_size = random.randint(1, int(max_tiles_per_cluster))
            self._grow_terrain_cluster(seed, cluster_size, terrain_type)
            created += 1

    def _grow_terrain_cluster(self, seed, target_size, terrain_type):
        frontier = [seed]
        placed = 0

        while frontier and placed < target_size:
            cell = frontier.pop(random.randrange(len(frontier)))
            if cell.terrain != TERRAIN_PLAIN:
                continue

            cell.terrain = terrain_type
            placed += 1

            neighbors = self.get_neighbors(cell.q, cell.r)
            random.shuffle(neighbors)
            for neighbor in neighbors:
                if neighbor.terrain == TERRAIN_PLAIN:
                    frontier.append(neighbor)
