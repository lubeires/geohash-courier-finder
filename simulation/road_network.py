"""Malha viária de BH (OpenStreetMap) e projeção de pontos na rua mais próxima.

Executar `python -m simulation.road_network` baixa o grafo para o cache local.
"""

import os
import time
from collections.abc import Sequence
from pathlib import Path

import osmnx as ox

from config import CACHE_DIR, GRAPH_PATH, PLACE_QUERY
from core.geometry import project_point_on_polyline

ox.settings.cache_folder = str(CACHE_DIR / "http")
ox.settings.requests_timeout = 300


def download_graph(path: Path = GRAPH_PATH, attempts: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            graph = ox.graph_from_place(PLACE_QUERY, network_type="drive")
            break
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(10 * attempt)
    # grava num arquivo temporário para não deixar um cache corrompido se o processo cair
    tmp = path.with_suffix(".tmp")
    ox.save_graphml(graph, tmp)
    os.replace(tmp, path)


class RoadNetwork:
    def __init__(self, graph) -> None:
        self._graph = graph
        self._polylines: dict[tuple[int, int, int], list[tuple[float, float]]] = {}

    @classmethod
    def load(cls, path: Path = GRAPH_PATH) -> "RoadNetwork":
        if not path.exists():
            print("Baixando a malha viária de Belo Horizonte (só na primeira execução, leva alguns minutos)...")
            download_graph(path)
        return cls(ox.load_graphml(path))

    def edge_polyline(self, u: int, v: int, k: int) -> list[tuple[float, float]]:
        """Pontos (lat, lon) da aresta. Sem o atributo geometry, a aresta é um segmento reto."""
        key = (u, v, k)
        polyline = self._polylines.get(key)
        if polyline is None:
            geometry = self._graph.edges[key].get("geometry")
            if geometry is not None:
                polyline = [(float(y), float(x)) for x, y in geometry.coords]
            else:
                nodes = self._graph.nodes
                polyline = [(nodes[u]["y"], nodes[u]["x"]), (nodes[v]["y"], nodes[v]["x"])]
            self._polylines[key] = polyline
        return polyline

    def snap(self, points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
        """Leva cada ponto (lat, lon) para a posição mais próxima sobre a rua mais próxima.

        O osmnx escolhe a aresta (em graus, pois o grafo não é projetado); a projeção sobre a
        polilinha da aresta é feita em metros.
        """
        if not points:
            return []
        edges = ox.distance.nearest_edges(self._graph, [p[1] for p in points], [p[0] for p in points])
        snapped = []
        for (lat, lon), (u, v, k) in zip(points, edges, strict=True):
            new_lat, new_lon, _ = project_point_on_polyline(lat, lon, self.edge_polyline(int(u), int(v), int(k)))
            snapped.append((new_lat, new_lon))
        return snapped

    def distance_to_nearest_edge_m(self, points: Sequence[tuple[float, float]]) -> list[float]:
        edges = ox.distance.nearest_edges(self._graph, [p[1] for p in points], [p[0] for p in points])
        return [
            project_point_on_polyline(lat, lon, self.edge_polyline(int(u), int(v), int(k)))[2]
            for (lat, lon), (u, v, k) in zip(points, edges, strict=True)
        ]


if __name__ == "__main__":
    download_graph()
    print(f"Grafo salvo em {GRAPH_PATH}")
