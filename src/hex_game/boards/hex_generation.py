"""Generic hex-grid feature generation helpers."""

from __future__ import annotations

import heapq
import math
import random
from typing import Callable

Coord = tuple[int, int]
Edge = tuple[Coord, Coord]
Vertex = tuple[int, int]


def edge_key(a, b):
    """Return a stable undirected edge key."""

    return (a, b) if a < b else (b, a)


def normalize_range_config(min_value, max_value, label):
    """Validate and normalize an integer [min, max] range."""

    min_value = int(min_value)
    max_value = int(max_value)
    if min_value < 0 or max_value < 0:
        raise ValueError(f"{label} cannot be negative")
    if max_value < min_value:
        raise ValueError(f"{label} has min ({min_value}) greater than max ({max_value})")
    return min_value, max_value


def normalize_cluster_config(min_clusters, max_clusters, max_tiles_per_cluster, label):
    """Validate and normalize cluster generation configuration."""

    min_clusters, max_clusters = normalize_range_config(
        min_clusters,
        max_clusters,
        f"{label} clusters",
    )
    max_tiles_per_cluster = int(max_tiles_per_cluster)
    if max_tiles_per_cluster < 0:
        raise ValueError(f"{label} max tiles per cluster cannot be negative")
    if max_clusters > 0 and max_tiles_per_cluster < 1:
        raise ValueError(f"{label} requires at least one tile per cluster")
    return min_clusters, max_clusters, max_tiles_per_cluster


def collect_adjacency_edges(coords, neighbor_coords_fn: Callable[[Coord], list[Coord]]) -> set[Edge]:
    """Collect unique undirected adjacency edges for a coordinate set."""

    coord_set = set(coords)
    edges = set()
    for coord in coord_set:
        for neighbor in neighbor_coords_fn(coord):
            if neighbor in coord_set and coord < neighbor:
                edges.add((coord, neighbor))
    return edges


def collect_boundary_coords(
    coords,
    neighbor_coords_fn: Callable[[Coord], list[Coord]],
    full_neighbor_degree: int = 6,
) -> list[Coord]:
    """Return coordinates that lie on a topology boundary."""

    coord_set = set(coords)
    boundary = []
    for coord in coord_set:
        internal_neighbors = [n for n in neighbor_coords_fn(coord) if n in coord_set]
        if len(internal_neighbors) < full_neighbor_degree:
            boundary.append(coord)
    return boundary


def _pick_cluster_seed(
    available_coords: set[Coord],
    is_interior_fn: Callable[[Coord], bool] | None,
    rng,
) -> Coord:
    if is_interior_fn is not None:
        interior = [coord for coord in available_coords if is_interior_fn(coord)]
        if interior:
            return rng.choice(interior)
    return rng.choice(tuple(available_coords))


def _grow_cluster(
    seed_coord: Coord,
    target_size: int,
    available_coords: set[Coord],
    neighbor_coords_fn: Callable[[Coord], list[Coord]],
    rng,
) -> list[Coord]:
    cluster = []
    cluster_set = set()
    frontier = [seed_coord]

    while frontier and len(cluster) < target_size:
        coord = frontier.pop(rng.randrange(len(frontier)))
        if coord not in available_coords:
            continue

        available_coords.remove(coord)
        cluster.append(coord)
        cluster_set.add(coord)

        neighbors = list(neighbor_coords_fn(coord))
        rng.shuffle(neighbors)
        for neighbor in neighbors:
            if neighbor in available_coords:
                frontier.append(neighbor)

    while len(cluster) < target_size and available_coords:
        border = [
            coord
            for coord in available_coords
            if any(neighbor in cluster_set for neighbor in neighbor_coords_fn(coord))
        ]

        if border:
            coord = rng.choice(border)
        else:
            coord = rng.choice(tuple(available_coords))

        available_coords.remove(coord)
        cluster.append(coord)
        cluster_set.add(coord)

    return cluster


def generate_clustered_regions(
    available_coords,
    neighbor_coords_fn: Callable[[Coord], list[Coord]],
    min_clusters: int,
    max_clusters: int,
    max_tiles_per_cluster: int,
    is_interior_fn: Callable[[Coord], bool] | None = None,
    rng: random.Random | None = None,
) -> list[list[Coord]]:
    """Generate connected coordinate clusters from available cells."""

    rng = rng or random
    available = set(available_coords)
    if max_clusters <= 0 or not available:
        return []

    max_placeable_clusters = min(int(max_clusters), len(available))
    if max_placeable_clusters < int(min_clusters):
        raise ValueError(
            f"cannot place minimum clusters ({min_clusters}); available cells: {len(available)}"
        )

    cluster_count = rng.randint(int(min_clusters), max_placeable_clusters)
    clusters = []

    for cluster_index in range(cluster_count):
        remaining_clusters = cluster_count - cluster_index
        remaining_cells = len(available)
        max_size_by_capacity = remaining_cells - (remaining_clusters - 1)
        max_cluster_size = min(int(max_tiles_per_cluster), max_size_by_capacity)
        if max_cluster_size <= 0:
            break

        target_size = rng.randint(1, max_cluster_size)
        seed = _pick_cluster_seed(available, is_interior_fn, rng)
        cluster_coords = _grow_cluster(seed, target_size, available, neighbor_coords_fn, rng)
        clusters.append(cluster_coords)

    return clusters


def _vertex_key(x, y, scale=1000):
    return (int(round(x * scale)), int(round(y * scale)))


def _vertex_distance_sq(a: Vertex, b: Vertex) -> int:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _cell_vertex_keys(
    coord: Coord,
    coord_to_pixel_fn: Callable[[int, int], tuple[float, float]],
    hex_radius: float,
) -> tuple[Vertex, ...]:
    x, y = coord_to_pixel_fn(coord[0], coord[1])
    vertices = []
    for i in range(6):
        angle = math.radians(60 * i)
        vx = x + hex_radius * math.cos(angle)
        vy = y + hex_radius * math.sin(angle)
        vertices.append(_vertex_key(vx, vy))
    return tuple(vertices)


def _build_boundary_edge_graph(
    coords,
    neighbor_coords_fn: Callable[[Coord], list[Coord]],
    coord_to_pixel_fn: Callable[[int, int], tuple[float, float]],
    hex_radius: float,
):
    coord_set = set(coords)
    if not coord_set:
        return None

    cell_vertices = {}
    side_counts = {}
    for coord in coord_set:
        vertices = _cell_vertex_keys(coord, coord_to_pixel_fn, hex_radius)
        cell_vertices[coord] = vertices
        for i in range(6):
            side = edge_key(vertices[i], vertices[(i + 1) % 6])
            side_counts[side] = side_counts.get(side, 0) + 1

    boundary_vertices = set()
    for side, count in side_counts.items():
        if count == 1:
            boundary_vertices.update(side)
    if not boundary_vertices:
        return None

    edge_vertices = {}
    vertex_graph = {}
    for coord in coord_set:
        shared_candidates = set(cell_vertices[coord])
        for neighbor in neighbor_coords_fn(coord):
            if neighbor not in coord_set:
                continue
            edge = edge_key(coord, neighbor)
            if edge in edge_vertices:
                continue

            shared_vertices = tuple(sorted(shared_candidates.intersection(cell_vertices[neighbor])))
            if len(shared_vertices) != 2:
                continue

            v1, v2 = shared_vertices
            edge_vertices[edge] = (v1, v2)
            vertex_graph.setdefault(v1, []).append((v2, edge))
            vertex_graph.setdefault(v2, []).append((v1, edge))

    if not edge_vertices:
        return None

    reachable_boundary_vertices = [v for v in boundary_vertices if v in vertex_graph]
    if len(reachable_boundary_vertices) < 2:
        return None

    xs = [v[0] for v in reachable_boundary_vertices]
    ys = [v[1] for v in reachable_boundary_vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    tolerance = max(1, int(round(hex_radius * 300)))

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


def _pick_boundary_endpoints(side_vertices, boundary_vertices, rng):
    axis_pairs = [("left", "right"), ("top", "bottom")]
    rng.shuffle(axis_pairs)

    for side_a, side_b in axis_pairs:
        start_pool = side_vertices.get(side_a, [])
        end_pool = side_vertices.get(side_b, [])
        if not start_pool or not end_pool:
            continue

        start = rng.choice(start_pool)
        ranked = sorted(
            end_pool,
            key=lambda v: _vertex_distance_sq(start, v),
            reverse=True,
        )
        candidate_count = min(8, len(ranked))
        end = rng.choice(ranked[:candidate_count])
        if start != end:
            return start, end

    all_boundary_vertices = list(boundary_vertices)
    if len(all_boundary_vertices) < 2:
        return None

    start = rng.choice(all_boundary_vertices)
    ranked = sorted(
        all_boundary_vertices,
        key=lambda v: _vertex_distance_sq(start, v),
        reverse=True,
    )
    for end in ranked:
        if start != end:
            return start, end

    return None


def _find_vertex_path(start_vertex, end_vertex, vertex_graph, used_edges: set[Edge], rng):
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
            step_cost = 1.0 + rng.random() * 0.35
            if edge in used_edges:
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


def _build_boundary_crossing_path(graph, min_length, used_edges: set[Edge], rng):
    vertex_graph = graph["vertex_graph"]
    boundary_vertices = graph["boundary_vertices"]
    side_vertices = graph["side_vertices"]

    for _ in range(28):
        endpoints = _pick_boundary_endpoints(side_vertices, boundary_vertices, rng)
        if endpoints is None:
            return None
        start_vertex, end_vertex = endpoints
        path_edges = _find_vertex_path(start_vertex, end_vertex, vertex_graph, used_edges, rng)
        if not path_edges:
            continue
        if len(path_edges) < min_length:
            continue
        if not any(edge not in used_edges for edge in path_edges):
            continue
        return path_edges

    for _ in range(12):
        endpoints = _pick_boundary_endpoints(side_vertices, boundary_vertices, rng)
        if endpoints is None:
            return None
        start_vertex, end_vertex = endpoints
        path_edges = _find_vertex_path(start_vertex, end_vertex, vertex_graph, used_edges, rng)
        if not path_edges:
            continue
        if any(edge not in used_edges for edge in path_edges):
            return path_edges

    return None


def generate_boundary_crossing_edges(
    coords,
    neighbor_coords_fn: Callable[[Coord], list[Coord]],
    coord_to_pixel_fn: Callable[[int, int], tuple[float, float]],
    hex_radius: float,
    min_paths: int,
    max_paths: int,
    min_path_length: int,
    existing_edges=None,
    rng: random.Random | None = None,
) -> set[Edge]:
    """Generate boundary-to-boundary edge paths over a hex dual graph."""

    rng = rng or random
    used_edges = set(existing_edges or set())
    min_paths = int(min_paths)
    max_paths = int(max_paths)

    if max_paths <= 0:
        return set()

    path_count = rng.randint(min_paths, max_paths)
    if path_count <= 0:
        return set()

    graph = _build_boundary_edge_graph(coords, neighbor_coords_fn, coord_to_pixel_fn, hex_radius)
    if graph is None:
        if min_paths > 0:
            raise ValueError("cannot build a boundary edge graph for this map shape")
        return set()

    created = 0
    attempts = 0
    generated_edges = set()

    while created < path_count and attempts < max(12, path_count * 24):
        attempts += 1
        path_edges = _build_boundary_crossing_path(graph, min_path_length, used_edges.union(generated_edges), rng)
        if not path_edges:
            continue
        generated_edges.update(path_edges)
        created += 1

    if created < min_paths:
        raise ValueError(
            f"could only place {created} edge paths, below minimum required {min_paths}"
        )

    return generated_edges


__all__ = [
    "edge_key",
    "normalize_range_config",
    "normalize_cluster_config",
    "collect_adjacency_edges",
    "collect_boundary_coords",
    "generate_clustered_regions",
    "generate_boundary_crossing_edges",
]
