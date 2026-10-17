import random

import pytest

from config import GRAPH_PATH

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


def test_point_in_the_lake_is_moved(network):
    # meio da lagoa da Pampulha
    lat, lon = network.snap([(-19.8510, -43.9790)])[0]
    assert (lat, lon) != (-19.8510, -43.9790)


def test_generation_with_snap_is_deterministic(network):
    from simulation.generator import generate_fleet

    centers = [("b1", -19.93, -43.94), ("b2", -19.85, -43.97)]
    a = generate_fleet(centers, 200, 400, seed=3, snap=network.snap)
    b = generate_fleet(centers, 200, 400, seed=3, snap=network.snap)
    assert a.couriers == b.couriers
