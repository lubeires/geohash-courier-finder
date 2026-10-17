"""Geração da frota sintética: normal bivariada em torno dos bares."""

import random
import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import perf_counter

from core.fleet_index import Courier, make_courier
from core.geometry import offset_to_degrees

# (id, lat, lon) de um centro da distribuição
Center = tuple[str, float, float]
SnapFunction = Callable[[Sequence[tuple[float, float]]], list[tuple[float, float]]]


@dataclass(frozen=True, slots=True)
class Fleet:
    couriers: tuple[Courier, ...]
    seed: int
    timings_ms: dict[str, float]


def resolve_seed(seed: int | None) -> int:
    return secrets.randbelow(1_000_000) if seed is None else seed


def allocate(n: int, num_centers: int, rng: random.Random) -> list[int]:
    """Quantos entregadores cada centro recebe. As quantidades diferem em no máximo 1."""
    if num_centers <= 0:
        raise ValueError("é preciso ao menos um centro")
    base, remainder = divmod(n, num_centers)
    counts = [base] * num_centers
    for i in rng.sample(range(num_centers), remainder):
        counts[i] += 1
    return counts


def sample_positions(
    centers: Sequence[Center], n: int, sigma_m: float, rng: random.Random
) -> list[tuple[str, float, float]]:
    """Sorteia N posições (origem, lat, lon) com deslocamentos N(0, σ) em metros."""
    positions = []
    for (center_id, lat, lon), count in zip(centers, allocate(n, len(centers), rng), strict=True):
        for _ in range(count):
            dlat, dlon = offset_to_degrees(rng.gauss(0, sigma_m), rng.gauss(0, sigma_m), lat)
            positions.append((center_id, lat + dlat, lon + dlon))
    return positions


def generate_fleet(
    centers: Sequence[Center],
    n: int,
    sigma_m: float,
    seed: int | None = None,
    snap: SnapFunction | None = None,
) -> Fleet:
    """Gera a frota. Sem `snap`, as posições ficam onde a normal as colocou."""
    if n < 1:
        raise ValueError(f"N deve ser positivo: {n}")
    seed = resolve_seed(seed)
    t0 = perf_counter()
    positions = sample_positions(centers, n, sigma_m, random.Random(seed))
    t1 = perf_counter()
    points = [(lat, lon) for _, lat, lon in positions]
    if snap is not None:
        points = snap(points)
    t2 = perf_counter()
    couriers = tuple(
        make_courier(f"E{i:05d}", lat, lon, origin_id)
        for i, ((origin_id, _, _), (lat, lon)) in enumerate(zip(positions, points, strict=True), start=1)
    )
    t3 = perf_counter()
    timings = {"sample": (t1 - t0) * 1000, "snap": (t2 - t1) * 1000, "total": (t3 - t0) * 1000}
    return Fleet(couriers, seed, timings)
