import random

import pytest

from core.fleet_index import FleetIndex, make_courier
from core.geometry import haversine_km


@pytest.fixture(scope="module")
def fleet():
    # 5 mil entregadores em 30 aglomerados dentro do retângulo de BH
    rng = random.Random(2026)
    centers = [(rng.uniform(-20.03, -19.80), rng.uniform(-44.04, -43.88)) for _ in range(30)]
    couriers = []
    for i in range(5000):
        lat, lon = rng.choice(centers)
        couriers.append(make_courier(f"E{i + 1:05d}", lat + rng.gauss(0, 0.01), lon + rng.gauss(0, 0.01)))
    return FleetIndex(couriers)


def test_query_equals_brute_force(fleet):
    rng = random.Random(7)
    crossed_border = False
    for _ in range(200):
        lat, lon = rng.uniform(-20.03, -19.80), rng.uniform(-44.04, -43.88)
        radius = rng.uniform(0.1, 10)
        result = fleet.query(lat, lon, radius, speed_kmh=20)
        expected = [(c.id, d) for c, d in fleet.brute_force(lat, lon, radius)]
        assert [(m.courier.id, m.distance_km) for m in result.accepted] == expected
        assert len(result.accepted) + len(result.rejected) == result.candidates_count
        center = result.cells[0]
        if any(m.courier.geohash[: result.precision] != center for m in result.accepted):
            crossed_border = True
    # sem a busca nas vizinhas, esses entregadores teriam ficado de fora
    assert crossed_border


def test_query_result_shape(fleet):
    result = fleet.query(-19.92, -43.94, 2, speed_kmh=20)
    assert result.precision == 5
    assert len(result.cells) == 9 == len(set(result.cells))
    assert all(len(cell) == 5 for cell in result.cells)
    assert set(result.timings_ms) == {"encode", "trie", "filter", "total"}
    assert all(v >= 0 for v in result.timings_ms.values())
    for match in result.accepted:
        assert match.eta_min == pytest.approx(match.distance_km / 20 * 60)
    distances = [m.distance_km for m in result.accepted]
    assert distances == sorted(distances)


def test_rejected_are_outside_radius(fleet):
    result = fleet.query(-19.92, -43.94, 1.5, speed_kmh=20)
    assert result.rejected
    assert all(haversine_km(-19.92, -43.94, c.lat, c.lon) > 1.5 for c in result.rejected)


def test_empty_fleet():
    result = FleetIndex([]).query(-19.92, -43.94, 2, speed_kmh=20)
    assert result.accepted == () and result.rejected == () and result.candidates_count == 0


def test_shared_geohash():
    index = FleetIndex([make_courier("E1", -19.92, -43.94), make_courier("E2", -19.92, -43.94)])
    result = index.query(-19.92, -43.94, 0.5, speed_kmh=20)
    assert [m.courier.id for m in result.accepted] == ["E1", "E2"]


def test_duplicate_id_rejected():
    with pytest.raises(ValueError):
        FleetIndex([make_courier("E1", -19.92, -43.94), make_courier("E1", -19.93, -43.94)])


@pytest.mark.parametrize(("radius", "speed"), [(0, 20), (-1, 20), (2, 0)])
def test_invalid_query(fleet, radius, speed):
    with pytest.raises(ValueError):
        fleet.query(-19.92, -43.94, radius, speed)


def test_make_courier_uses_storage_precision():
    courier = make_courier("E1", -19.923021, -43.943333, origin_id="114942")
    assert courier.geohash == "7h2y8j17"
    assert courier.origin_id == "114942"
