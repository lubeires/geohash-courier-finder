"""Índice da frota: geohash dos entregadores numa Trie compacta + filtragem por raio."""

from collections.abc import Iterable
from dataclasses import dataclass
from time import perf_counter
from typing import NamedTuple

from core.constants import STORAGE_PRECISION
from core.geohash import encode, neighbors
from core.geometry import bbox_around, haversine_km, precision_for_radius
from core.trie import CompactTrie


@dataclass(frozen=True, slots=True)
class Courier:
    id: str
    lat: float
    lon: float
    geohash: str
    origin_id: str = ""


class Match(NamedTuple):
    courier: Courier
    distance_km: float
    eta_min: float


@dataclass(frozen=True, slots=True)
class QueryResult:
    accepted: tuple[Match, ...]
    # candidatos que a Trie devolveu, mas que estão fora do raio
    rejected: tuple[Courier, ...]
    # célula central primeiro, depois as vizinhas na ordem n, ne, e, se, s, sw, w, nw
    cells: tuple[str, ...]
    precision: int
    candidates_count: int
    timings_ms: dict[str, float]


def make_courier(courier_id: str, lat: float, lon: float, origin_id: str = "") -> Courier:
    return Courier(courier_id, lat, lon, encode(lat, lon, STORAGE_PRECISION), origin_id)


class FleetIndex:
    """Índice imutável de uma frota. Uma frota nova gera um índice novo."""

    __slots__ = ("_trie", "_by_id")

    def __init__(self, couriers: Iterable[Courier]) -> None:
        self._trie = CompactTrie()
        self._by_id: dict[str, Courier] = {}
        for courier in couriers:
            if courier.id in self._by_id:
                raise ValueError(f"entregador repetido: {courier.id}")
            self._by_id[courier.id] = courier
            self._trie.insert(courier.geohash, courier)

    def __len__(self) -> int:
        return len(self._by_id)

    def couriers(self) -> tuple[Courier, ...]:
        return tuple(self._by_id.values())

    def get(self, courier_id: str) -> Courier | None:
        return self._by_id.get(courier_id)

    def stats(self) -> dict:
        return self._trie.stats()

    def query(self, lat: float, lon: float, radius_km: float, speed_kmh: float) -> QueryResult:
        """Entregadores a até `radius_km` de (lat, lon), do mais próximo ao mais distante."""
        if radius_km <= 0 or speed_kmh <= 0:
            raise ValueError("raio e velocidade devem ser positivos")

        t0 = perf_counter()
        precision = precision_for_radius(radius_km, lat)
        center = encode(lat, lon, precision)
        # nos polos uma vizinha pode repetir a própria célula
        cells = tuple(dict.fromkeys((center, *neighbors(center).values())))
        t1 = perf_counter()

        # células de mesma precisão são disjuntas: nenhum entregador aparece duas vezes
        candidates = []
        for cell in cells:
            candidates.extend(self._trie.search_prefix(cell))
        t2 = perf_counter()

        # A caixa que contém o círculo descarta a maior parte dos rejeitados com duas
        # comparações; só quem está dentro dela paga o cálculo do Haversine.
        (south, west), (north, east) = bbox_around(lat, lon, radius_km)
        accepted, rejected = [], []
        for courier in candidates:
            if south <= courier.lat <= north and west <= courier.lon <= east:
                distance = haversine_km(lat, lon, courier.lat, courier.lon)
                if distance <= radius_km:
                    accepted.append((courier, distance))
                    continue
            rejected.append(courier)
        t3 = perf_counter()

        accepted.sort(key=lambda item: (item[1], item[0].id))
        matches = tuple(Match(c, d, d / speed_kmh * 60) for c, d in accepted)
        t4 = perf_counter()

        return QueryResult(
            accepted=matches,
            rejected=tuple(rejected),
            cells=cells,
            precision=precision,
            candidates_count=len(candidates),
            timings_ms={
                "encode": (t1 - t0) * 1000,
                "trie": (t2 - t1) * 1000,
                "filter": (t3 - t2) * 1000,
                "total": (t4 - t0) * 1000,
            },
        )

    def brute_force(self, lat: float, lon: float, radius_km: float) -> list[tuple[Courier, float]]:
        """Mesma consulta sem índice: calcula a distância para todos os entregadores."""
        found = []
        for courier in self._by_id.values():
            distance = haversine_km(lat, lon, courier.lat, courier.lon)
            if distance <= radius_km:
                found.append((courier, distance))
        found.sort(key=lambda item: (item[1], item[0].id))
        return found
