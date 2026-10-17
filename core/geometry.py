"""Distâncias na esfera, escolha da precisão do geohash e projeção em polilinhas."""

import math
from collections.abc import Sequence

from core.constants import EARTH_RADIUS_KM, METERS_PER_DEGREE, STORAGE_PRECISION
from core.geohash import cell_degrees, decode_bbox, encode


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância de círculo máximo entre dois pontos, em km."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def precision_for_radius(radius_km: float, lat: float) -> int:
    """Maior precisão em que o bloco 3x3 de células em torno de `lat` cobre o raio.

    A altura da célula é exata (arco de meridiano). Para a largura usa-se a menor
    distância de um ponto da célula até o meridiano da borda, R·asin(cos φ·sin Δλ),
    tomada na borda da célula mais distante do equador, onde ela é mínima.
    """
    if radius_km <= 0:
        raise ValueError(f"raio deve ser positivo: {radius_km}")
    for precision in range(STORAGE_PRECISION, 0, -1):
        lat_min, lat_max, _, _ = decode_bbox(encode(lat, 0.0, precision))
        phi_far = math.radians(max(abs(lat_min), abs(lat_max)))
        dlat, dlon = cell_degrees(precision)
        height = EARTH_RADIUS_KM * math.radians(dlat)
        width = EARTH_RADIUS_KM * math.asin(math.cos(phi_far) * math.sin(math.radians(dlon)))
        if height >= radius_km and width >= radius_km:
            return precision
    raise ValueError(f"raio grande demais para a busca por vizinhança: {radius_km} km")


def offset_to_degrees(dy_m: float, dx_m: float, lat: float) -> tuple[float, float]:
    """Converte um deslocamento local (norte, leste) em metros para (Δlat, Δlon) em graus."""
    return dy_m / METERS_PER_DEGREE, dx_m / (METERS_PER_DEGREE * math.cos(math.radians(lat)))


def project_point_on_polyline(
    lat: float, lon: float, polyline: Sequence[tuple[float, float]]
) -> tuple[float, float, float]:
    """Ponto da polilinha mais próximo de (lat, lon). Devolve (lat, lon, distância em m).

    Trabalha num plano equirretangular centrado no próprio ponto, o que é preciso para
    as distâncias de poucas centenas de metros envolvidas.
    """
    if not polyline:
        raise ValueError("polilinha vazia")
    scale_x = math.cos(math.radians(lat)) * METERS_PER_DEGREE

    def to_plane(p: tuple[float, float]) -> tuple[float, float]:
        return (p[1] - lon) * scale_x, (p[0] - lat) * METERS_PER_DEGREE

    best = (math.inf, 0.0, 0.0)
    ax, ay = to_plane(polyline[0])
    if len(polyline) == 1:
        best = (math.hypot(ax, ay), ax, ay)
    for point in polyline[1:]:
        bx, by = to_plane(point)
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        # o ponto consultado é a origem do plano
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length2))
        px, py = ax + t * dx, ay + t * dy
        dist = math.hypot(px, py)
        if dist < best[0]:
            best = (dist, px, py)
        ax, ay = bx, by

    dist, px, py = best
    return lat + py / METERS_PER_DEGREE, lon + px / scale_x, dist


def bbox_around(lat: float, lon: float, radius_km: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """Menor caixa ((sul, oeste), (norte, leste)) que contém o círculo de raio `radius_km`.

    Na esfera, o círculo se estende Δφ = r/R em latitude e Δλ = asin(sin(r/R) / cos φ)
    em longitude. Vale enquanto o círculo não alcança um polo.
    """
    angle = radius_km / EARTH_RADIUS_KM
    dlat = math.degrees(angle)
    dlon = math.degrees(math.asin(min(1.0, math.sin(angle) / math.cos(math.radians(lat)))))
    return (lat - dlat, lon - dlon), (lat + dlat, lon + dlon)
