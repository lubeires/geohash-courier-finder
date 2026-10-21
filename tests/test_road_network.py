import random

import pytest

from config import GRAPH_PATH
from core.geometry import haversine_km

pytestmark = [
    pytest.mark.graph,
    pytest.mark.skipif(not GRAPH_PATH.exists(), reason="grafo não está em cache"),
]


@pytest.fixture(scope="module")
def network():
    from simulation.road_network import RoadNetwork

    return RoadNetwork.load()


def test_snapped_points_are_on_the_road(network):
    rng = random.Random(42)
    points = [(rng.gauss(-19.92, 0.03), rng.gauss(-43.94, 0.03)) for _ in range(500)]
    snapped = network.snap(points)
    assert len(snapped) == len(points)
    assert max(network.distance_to_nearest_edge_m(snapped)) < 1.0


def test_snap_is_idempotent(network):
    rng = random.Random(7)
    points = [(rng.gauss(-19.92, 0.03), rng.gauss(-43.94, 0.03)) for _ in range(300)]
    once = network.snap(points)
    twice = network.snap(once)
    assert max(haversine_km(*a, *b) for a, b in zip(once, twice, strict=True)) < 0.001


def test_snap_moves_point_by_its_distance_to_the_road(network):
    rng = random.Random(9)
    points = [(rng.gauss(-19.92, 0.03), rng.gauss(-43.94, 0.03)) for _ in range(300)]
    snapped = network.snap(points)
    expected = network.distance_to_nearest_edge_m(points)
    for p, q, d in zip(points, snapped, expected, strict=True):
        assert abs(haversine_km(*p, *q) * 1000 - d) < 1.0


def test_point_in_the_lake_is_moved_to_the_shore(network):
    # meio da lagoa da Pampulha
    lake = (-19.8510, -43.9790)
    lat, lon = network.snap([lake])[0]
    assert haversine_km(*lake, lat, lon) > 0.1


def test_generation_with_snap_is_deterministic(network):
    from simulation.generator import generate_fleet

    centers = [("b1", -19.93, -43.94), ("b2", -19.85, -43.97)]
    a = generate_fleet(centers, 200, 400, seed=3, snap=network.snap)
    b = generate_fleet(centers, 200, 400, seed=3, snap=network.snap)
    assert a.couriers == b.couriers
