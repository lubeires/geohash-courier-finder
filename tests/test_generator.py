import math
import random
import statistics

import pytest

from core.constants import METERS_PER_DEGREE
from simulation.generator import allocate, generate_fleet

CENTERS = [("b1", -19.93, -43.94), ("b2", -19.85, -43.97), ("b3", -19.97, -44.01)]


def test_same_seed_same_fleet():
    a = generate_fleet(CENTERS, 500, 400, seed=42)
    b = generate_fleet(CENTERS, 500, 400, seed=42)
    assert a.couriers == b.couriers
    assert generate_fleet(CENTERS, 500, 400, seed=43).couriers != a.couriers


def test_seed_is_reported():
    fleet = generate_fleet(CENTERS, 10, 400)
    assert generate_fleet(CENTERS, 10, 400, seed=fleet.seed).couriers == fleet.couriers


@pytest.mark.parametrize(("n", "centers"), [(1000, 3), (7, 3), (2, 5), (4715, 4715), (1, 4715)])
def test_allocation_is_even(n, centers):
    counts = allocate(n, centers, random.Random(1))
    assert sum(counts) == n
    assert max(counts) - min(counts) <= 1


def test_ids_and_origins():
    fleet = generate_fleet(CENTERS, 7, 400, seed=1)
    assert [c.id for c in fleet.couriers] == [f"E{i:05d}" for i in range(1, 8)]
    assert {c.origin_id for c in fleet.couriers} <= {"b1", "b2", "b3"}
    assert all(len(c.geohash) == 8 for c in fleet.couriers)


def test_gaussian_spread():
    fleet = generate_fleet([("b1", -19.93, -43.94)], 20_000, 400, seed=5)
    dy = [(c.lat + 19.93) * METERS_PER_DEGREE for c in fleet.couriers]
    dx = [(c.lon + 43.94) * METERS_PER_DEGREE * math.cos(math.radians(-19.93)) for c in fleet.couriers]
    assert statistics.pstdev(dy) == pytest.approx(400, rel=0.05)
    assert statistics.pstdev(dx) == pytest.approx(400, rel=0.05)
    assert abs(statistics.mean(dy)) < 15


def test_snap_is_applied():
    fleet = generate_fleet(CENTERS, 5, 400, seed=1, snap=lambda pts: [(-19.9, -43.9)] * len(pts))
    assert all((c.lat, c.lon) == (-19.9, -43.9) for c in fleet.couriers)
    assert set(fleet.timings_ms) == {"sample", "snap", "total"}


def test_invalid_n():
    with pytest.raises(ValueError):
        generate_fleet(CENTERS, 0, 400)
