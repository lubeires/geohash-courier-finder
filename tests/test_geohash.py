import random

import pytest

from core.constants import BASE32
from core.geohash import DIRECTIONS, cell_size_m, decode, decode_bbox, encode, neighbors


@pytest.mark.parametrize(
    ("lat", "lon", "precision", "expected"),
    [
        (42.6, -5.6, 5, "ezs42"),
        (57.64911, 10.40744, 11, "u4pruydqqvj"),
        (-19.923021, -43.943333, 8, "7h2y8j17"),
    ],
)
def test_known_vectors(lat, lon, precision, expected):
    assert encode(lat, lon, precision) == expected


def test_decode_ezs42():
    lat, lon = decode("ezs42")
    assert lat == pytest.approx(42.605, abs=0.03)
    assert lon == pytest.approx(-5.603, abs=0.03)


def test_round_trip():
    rng = random.Random(1)
    for _ in range(10_000):
        lat, lon = rng.uniform(-90, 90), rng.uniform(-180, 180)
        precision = rng.randint(1, 12)
        gh = encode(lat, lon, precision)
        lat_min, lat_max, lon_min, lon_max = decode_bbox(gh)
        assert lat_min <= lat < lat_max or lat == lat_max == 90
        assert lon_min <= lon < lon_max or lon == lon_max == 180
        assert encode(*decode(gh), precision) == gh


def test_point_on_division_goes_to_upper_half():
    assert encode(0.0, 0.0, 1) == "s"
    assert encode(90.0, 180.0, 2) == "zz"
    assert encode(-90.0, -180.0, 2) == "00"


def test_prefix_is_parent_cell():
    gh = encode(-19.93, -43.94, 8)
    for p in range(1, 8):
        assert encode(-19.93, -43.94, p) == gh[:p]


def _sample_cells():
    rng = random.Random(207)
    cells = []
    for _ in range(5000):
        lat = rng.uniform(-85, 85)
        cells.append(encode(lat, rng.uniform(-180, 180), rng.randint(1, 8)))
    # todas as filhas de pais aleatórios, o que inclui as que ficam na borda do pai
    for _ in range(160):
        parent = encode(rng.uniform(-85, 85), rng.uniform(-180, 180), rng.randint(1, 7))
        cells.extend(parent + c for c in BASE32)
    return cells


def _wrap(lon):
    return (lon + 180) % 360 - 180


def test_neighbors_are_adjacent_boxes():
    # cada vizinha tem o mesmo tamanho e ocupa a posição esperada em relação à célula
    for gh in _sample_cells():
        south, north, west, east = decode_bbox(gh)
        if south == -90 or north == 90:
            continue  # nos polos a vizinha repete a linha (ver test_pole_saturates)
        height, width = north - south, east - west
        result = neighbors(gh)
        assert len(set(result.values())) == 8 and gh not in result.values()
        for name, (dlat, dlon) in DIRECTIONS.items():
            s, n, w, e = decode_bbox(result[name])
            assert (n - s, e - w) == (height, width), (gh, name)
            assert s == south + dlat * height, (gh, name)
            assert _wrap(w) == _wrap(west + dlon * width), (gh, name)


def test_pole_saturates():
    top = encode(89.9, 10.0, 2)
    assert neighbors(top)["n"] == top
    assert neighbors(top)["ne"] == neighbors(top)["e"]


def test_neighbors_touch_the_cell():
    gh = "7h2x6"
    s0, n0, w0, e0 = decode_bbox(gh)
    for name, nb in neighbors(gh).items():
        s, n, w, e = decode_bbox(nb)
        assert len(nb) == len(gh)
        assert max(s, s0) <= min(n, n0) and max(w, w0) <= min(e, e0), name


def test_neighbor_across_parent_border():
    # "7h2xz" está na borda leste do pai "7h2x"; a vizinha leste já pertence a "7h2z"
    assert neighbors("7h2xz")["e"] == "7h2zb"
    assert neighbors("7h2zb")["w"] == "7h2xz"


def test_antimeridian_wraps():
    west_edge = encode(0.1, -179.99, 3)
    assert decode(neighbors(west_edge)["w"])[1] > 170


def test_cell_size_in_bh():
    height, width = cell_size_m(5, -19.92)
    assert height == pytest.approx(4886, rel=0.01)
    assert width == pytest.approx(4598, rel=0.01)


@pytest.mark.parametrize("bad", ["", "abc", "7h2xa", "x" * 13])
def test_invalid_geohash(bad):
    with pytest.raises(ValueError):
        decode_bbox(bad)


INVALID_POINTS = [(91, 0, 5), (0, 181, 5), (float("nan"), 0, 5), (0, 0, 0), (0, 0, 13)]


@pytest.mark.parametrize(("lat", "lon", "precision"), INVALID_POINTS)
def test_invalid_encode(lat, lon, precision):
    with pytest.raises(ValueError):
        encode(lat, lon, precision)
