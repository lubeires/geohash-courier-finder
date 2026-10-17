"""Geohash em Base32: bissecção alternada dos intervalos de longitude e latitude.

A cada passo, o intervalo de um dos eixos é dividido ao meio e o bit diz em qual
metade o ponto está (1 = metade superior). Os passos alternam começando pela
longitude, e cada grupo de 5 bits vira um caractere.
"""

import math

from core.constants import BASE32, MAX_PRECISION, METERS_PER_DEGREE

_DECODE = {c: i for i, c in enumerate(BASE32)}

# (deslocamento em células de latitude, deslocamento em células de longitude)
DIRECTIONS = {
    "n": (1, 0),
    "ne": (1, 1),
    "e": (0, 1),
    "se": (-1, 1),
    "s": (-1, 0),
    "sw": (-1, -1),
    "w": (0, -1),
    "nw": (1, -1),
}


def cell_degrees(precision: int) -> tuple[float, float]:
    """Dimensões (altura, largura) da célula em graus.

    Dos 5p bits, a longitude fica com os de posição par (metade arredondada para cima)
    e a latitude com o restante.
    """
    total = 5 * precision
    lon_bits, lat_bits = (total + 1) // 2, total // 2
    return 180 / 2**lat_bits, 360 / 2**lon_bits


def _check_precision(precision: int) -> None:
    if not isinstance(precision, int) or not 1 <= precision <= MAX_PRECISION:
        raise ValueError(f"precisão deve estar entre 1 e {MAX_PRECISION}: {precision!r}")


def encode(lat: float, lon: float, precision: int = 8) -> str:
    """Codifica (lat, lon) em `precision` caracteres. O(p).

    Um ponto exatamente sobre uma divisão fica na metade superior (leste/norte).
    """
    _check_precision(precision)
    if not (math.isfinite(lat) and math.isfinite(lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"coordenada inválida: ({lat}, {lon})")

    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    chars = []
    value = 0
    for i in range(5 * precision):
        if i % 2 == 0:
            mid = (lon_lo + lon_hi) / 2
            bit = lon >= mid
            if bit:
                lon_lo = mid
            else:
                lon_hi = mid
        else:
            mid = (lat_lo + lat_hi) / 2
            bit = lat >= mid
            if bit:
                lat_lo = mid
            else:
                lat_hi = mid
        value = value * 2 + bit
        if i % 5 == 4:
            chars.append(BASE32[value])
            value = 0
    return "".join(chars)


def decode_bbox(gh: str) -> tuple[float, float, float, float]:
    """Caixa (lat_min, lat_max, lon_min, lon_max) da célula. O(p).

    Refaz as mesmas bissecções do `encode`, agora lendo os bits do geohash.
    """
    if not gh or len(gh) > MAX_PRECISION:
        raise ValueError(f"geohash inválido: {gh!r}")

    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    i = 0
    for c in gh.lower():
        if c not in _DECODE:
            raise ValueError(f"caractere inválido no geohash: {c!r}")
        value = _DECODE[c]
        for shift in range(4, -1, -1):
            bit = (value >> shift) & 1
            if i % 2 == 0:
                mid = (lon_lo + lon_hi) / 2
                if bit:
                    lon_lo = mid
                else:
                    lon_hi = mid
            else:
                mid = (lat_lo + lat_hi) / 2
                if bit:
                    lat_lo = mid
                else:
                    lat_hi = mid
            i += 1
    return lat_lo, lat_hi, lon_lo, lon_hi


def decode(gh: str) -> tuple[float, float]:
    """Centro (lat, lon) da célula."""
    lat_min, lat_max, lon_min, lon_max = decode_bbox(gh)
    return (lat_min + lat_max) / 2, (lon_min + lon_max) / 2


def neighbors(gh: str) -> dict[str, str]:
    """As 8 células vizinhas, de mesma precisão. O(p).

    Parte do centro da célula, anda exatamente uma célula em cada direção e recodifica.
    O ponto obtido é o centro da vizinha, nunca uma fronteira, e o `encode` cuida dos
    casos em que a vizinha pertence a outra célula-pai (prefixo diferente).
    """
    precision = len(gh)
    lat, lon = decode(gh)
    height, width = cell_degrees(precision)
    result = {}
    for name, (dlat, dlon) in DIRECTIONS.items():
        new_lat = lat + dlat * height
        if not -90 < new_lat < 90:
            # além do polo não há vizinha: fica na mesma linha
            new_lat = lat
        # a longitude dá a volta no antimeridiano
        new_lon = (lon + dlon * width + 180) % 360 - 180
        result[name] = encode(new_lat, new_lon, precision)
    return result


def cell_size_m(precision: int, lat: float) -> tuple[float, float]:
    """Dimensões aproximadas (altura, largura) da célula em metros, na latitude dada."""
    _check_precision(precision)
    dlat, dlon = cell_degrees(precision)
    return dlat * METERS_PER_DEGREE, dlon * METERS_PER_DEGREE * math.cos(math.radians(lat))
