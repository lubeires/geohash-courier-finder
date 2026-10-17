import math
import random

import pytest

from core.constants import EARTH_RADIUS_KM
from core.geohash import encode, neighbors
from core.geometry import (
    bbox_around,
    haversine_km,
    offset_to_degrees,
    precision_for_radius,
    project_point_on_polyline,
)

BH_LAT = -19.92


def destination(lat, lon, bearing_deg, distance_km):
    # ponto a uma distância e azimute dados, na esfera (fórmula direta)
    phi1, lambda1 = math.radians(lat), math.radians(lon)
    theta = math.radians(bearing_deg)
    delta = distance_km / EARTH_RADIUS_KM
    phi2 = math.asin(math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta))
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1), math.cos(delta) - math.sin(phi1) * math.sin(phi2)
    )
    return math.degrees(phi2), math.degrees(lambda2)


def test_haversine_basics():
    assert haversine_km(-19.9, -43.9, -19.9, -43.9) == 0
    a, b = (-19.92, -43.94), (-19.85, -43.97)
    assert haversine_km(*a, *b) == pytest.approx(haversine_km(*b, *a))
    assert haversine_km(0, 0, 1, 0) == pytest.approx(111.195, abs=1e-3)
    assert haversine_km(0, 0, 0, 180) == pytest.approx(math.pi * EARTH_RADIUS_KM)


def test_haversine_matches_destination():
    lat, lon = destination(BH_LAT, -43.94, 37, 2.5)
    assert haversine_km(BH_LAT, -43.94, lat, lon) == pytest.approx(2.5, rel=1e-9)


@pytest.mark.parametrize(
    ("radius", "expected"),
    [(0.1, 7), (0.14, 7), (0.2, 6), (0.61, 6), (0.62, 5), (2, 5), (4.5, 5), (5, 4), (10, 4)],
)
def test_precision_for_radius_in_bh(radius, expected):
    assert precision_for_radius(radius, BH_LAT) == expected


def test_precision_for_radius_rejects_invalid():
    with pytest.raises(ValueError):
        precision_for_radius(0, BH_LAT)
    with pytest.raises(ValueError):
        precision_for_radius(10_000, BH_LAT)


def test_nine_cells_cover_the_circle():
    rng = random.Random(11)
    for _ in range(2000):
        lat = rng.uniform(-20.06, -19.77)
        lon = rng.uniform(-44.06, -43.86)
        radius = rng.uniform(0.1, 10)
        p = precision_for_radius(radius, lat)
        center = encode(lat, lon, p)
        cells = {center, *neighbors(center).values()}
        for _ in range(10):
            # pontos na borda do círculo são o pior caso
            distance = radius * (1 - 1e-9) * math.sqrt(rng.random()) if rng.random() < 0.5 else radius * (1 - 1e-9)
            point = destination(lat, lon, rng.uniform(0, 360), distance)
            assert encode(*point, p) in cells, (lat, lon, radius)


def test_offset_to_degrees():
    dlat, dlon = offset_to_degrees(1000, 1000, BH_LAT)
    assert haversine_km(BH_LAT, -43.94, BH_LAT + dlat, -43.94) == pytest.approx(1.0, rel=1e-6)
    assert haversine_km(BH_LAT, -43.94, BH_LAT, -43.94 + dlon) == pytest.approx(1.0, rel=1e-4)


def test_projection_on_segment_interior():
    segment = [(-19.92, -43.95), (-19.92, -43.93)]
    lat, lon, dist = project_point_on_polyline(-19.919, -43.94, segment)
    assert lat == pytest.approx(-19.92, abs=1e-9)
    assert lon == pytest.approx(-43.94, abs=1e-9)
    assert dist == pytest.approx(111.2, abs=0.5)


def test_projection_clamps_to_endpoint():
    segment = [(-19.92, -43.95), (-19.92, -43.93)]
    lat, lon, _ = project_point_on_polyline(-19.92, -43.90, segment)
    assert (lat, lon) == pytest.approx((-19.92, -43.93))


def test_projection_chooses_closest_segment():
    polyline = [(-19.92, -43.95), (-19.92, -43.94), (-19.90, -43.94)]
    lat, lon, _ = project_point_on_polyline(-19.91, -43.9395, polyline)
    assert lon == pytest.approx(-43.94, abs=1e-9)
    assert lat == pytest.approx(-19.91, abs=1e-9)


def test_projection_degenerate_segment():
    lat, lon, dist = project_point_on_polyline(-19.91, -43.94, [(-19.92, -43.94), (-19.92, -43.94)])
    assert (lat, lon) == pytest.approx((-19.92, -43.94))
    assert dist == pytest.approx(1112, abs=1)
    with pytest.raises(ValueError):
        project_point_on_polyline(-19.91, -43.94, [])


def test_bbox_around_contains_circle():
    (south, west), (north, east) = bbox_around(BH_LAT, -43.94, 2)
    for bearing in range(0, 360, 15):
        lat, lon = destination(BH_LAT, -43.94, bearing, 2)
        assert south - 1e-6 <= lat <= north + 1e-6
        assert west - 1e-6 <= lon <= east + 1e-6
