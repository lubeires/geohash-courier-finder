from app.callbacks import FleetState, candidates_geojson, fleet_geojson, fmt, results_table, validation_error
from app.main import create_app
from config import FLEET_SIZE
from core.fleet_index import FleetIndex
from simulation.generator import generate_fleet

CENTERS = [("b1", -19.93, -43.94), ("b2", -19.85, -43.97)]


def positions(collection):
    return sorted(tuple(f["geometry"]["coordinates"]) for f in collection["features"])


def test_new_fleet_replaces_the_old_one():
    state = FleetState()
    fleet_a = generate_fleet(CENTERS, 300, 400, seed=1)
    gen_a = state.replace(FleetIndex(fleet_a.couriers))
    fleet_b = generate_fleet(CENTERS, 120, 400, seed=2)
    gen_b = state.replace(FleetIndex(fleet_b.couriers))

    assert state.get(gen_a) is None
    index = state.get(gen_b)
    assert len(index) == 120
    expected = sorted((round(c.lon, 6), round(c.lat, 6)) for c in fleet_b.couriers)
    assert positions(fleet_geojson(index.couriers())) == expected
    # os ids recomeçam a cada geração; o que importa é que só as posições novas existem
    assert {(c.lat, c.lon) for c in index.couriers()} == {(c.lat, c.lon) for c in fleet_b.couriers}


def test_candidates_geojson_marks_accepted_and_rejected():
    fleet = generate_fleet(CENTERS, 500, 400, seed=3)
    result = FleetIndex(fleet.couriers).query(-19.93, -43.94, 0.5, speed_kmh=20)
    features = candidates_geojson(result)["features"]
    accepted = [f for f in features if f["properties"]["accepted"]]
    assert len(accepted) == len(result.accepted)
    assert len(features) == result.candidates_count
    # o mais próximo é desenhado por último, por cima dos outros
    nearest = result.accepted[0].courier
    assert features[-1]["geometry"]["coordinates"] == [round(nearest.lon, 6), round(nearest.lat, 6)]


def test_table_lists_every_accepted_courier():
    fleet = generate_fleet(CENTERS, 2000, 400, seed=4)
    result = FleetIndex(fleet.couriers).query(-19.93, -43.94, 3, speed_kmh=20)
    (wrapper,) = results_table(result, 3)
    table = wrapper.children[1].children
    tbody = table.children[2]
    assert len(tbody.children) == len(result.accepted) > 0


def test_formatting_and_validation():
    assert fmt(1234.5, 1) == "1.234,5"
    assert fmt(20000) == "20.000"
    assert validation_error(1000, FLEET_SIZE, integer=True) == ""
    assert validation_error(0, FLEET_SIZE, integer=True)
    assert validation_error(None, FLEET_SIZE, integer=True)
    assert validation_error(10.5, FLEET_SIZE, integer=True)


def test_app_builds_without_road_network():
    app = create_app(network=None)
    assert app.layout is not None
