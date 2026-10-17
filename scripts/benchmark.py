"""Experimentos do relatório: busca indexada x varredura linear.

Uso: python -m scripts.benchmark [--repeats 30] [--seed 2026] [--out docs/results]

As frotas são geradas sem a projeção viária, que não muda o custo da busca e exigiria o
grafo do OpenStreetMap.
"""

import argparse
import csv
import gc
import platform
import statistics
from pathlib import Path
from time import perf_counter

from catalog.restaurants import RestaurantCatalog
from config import BAR_CATEGORIES, RESTAURANTS_CSV, ROOT, SIGMA_M
from core.fleet_index import FleetIndex
from core.geometry import bbox_around, haversine_km
from scripts.svg_chart import line_chart, stacked_bars
from simulation.generator import generate_fleet

FLEET_SIZES = [1000, 5000, 10_000, 20_000]
RADII_KM = [0.5, 1, 2, 5]
REFERENCE_RESTAURANTS = {
    "286": "Savassi",
    "114942": "Centro",
    "30610": "Pampulha",
    "1020": "Barreiro",
    "187332": "Borda de célula",
}


def linear_scan(couriers, lat, lon, radius_km):
    return [c for c in couriers if haversine_km(lat, lon, c.lat, c.lon) <= radius_km]


def linear_scan_bbox(couriers, lat, lon, radius_km):
    (south, west), (north, east) = bbox_around(lat, lon, radius_km)
    return [
        c
        for c in couriers
        if south <= c.lat <= north and west <= c.lon <= east and haversine_km(lat, lon, c.lat, c.lon) <= radius_km
    ]


def median_ms(fn, repeats: int) -> float:
    for _ in range(3):
        fn()
    samples = []
    gc.collect()
    gc.disable()
    try:
        for _ in range(repeats):
            start = perf_counter()
            fn()
            samples.append((perf_counter() - start) * 1000)
    finally:
        gc.enable()
    return statistics.median(samples)


def measure(index, couriers, lat, lon, radius, repeats) -> dict:
    """Medianas da consulta indexada e das duas varreduras lineares, em ms."""
    return {
        "indexed_ms": round(median_ms(lambda: index.query(lat, lon, radius, 20), repeats), 4),
        "linear_ms": round(median_ms(lambda: linear_scan(couriers, lat, lon, radius), repeats), 4),
        "linear_bbox_ms": round(median_ms(lambda: linear_scan_bbox(couriers, lat, lon, radius), repeats), 4),
    }


def run(repeats: int, seed: int, out: Path) -> list[dict]:
    catalog = RestaurantCatalog.load(RESTAURANTS_CSV)
    centers = [(r.id, r.lat, r.lon) for r in catalog.with_categories(BAR_CATEGORIES)]
    restaurants = [catalog.get(rid) for rid in REFERENCE_RESTAURANTS]

    rows, builds = [], []
    for n in FLEET_SIZES:
        fleet = generate_fleet(centers, n, SIGMA_M.default, seed=seed)
        start = perf_counter()
        index = FleetIndex(fleet.couriers)
        build_ms = (perf_counter() - start) * 1000
        builds.append({"n": n, "build_ms": round(build_ms, 2), **index.stats()})
        couriers = index.couriers()
        print(f"N = {n}: índice construído em {build_ms:.0f} ms")

        for restaurant in restaurants:
            for radius in RADII_KM:
                lat, lon = restaurant.lat, restaurant.lon
                result = index.query(lat, lon, radius, 20)
                stages = [index.query(lat, lon, radius, 20).timings_ms for _ in range(repeats)]
                rows.append(
                    {
                        "n": n,
                        "restaurant": REFERENCE_RESTAURANTS[restaurant.id],
                        "radius_km": radius,
                        "precision": result.precision,
                        "candidates": result.candidates_count,
                        "accepted": len(result.accepted),
                        **{f"{k}_ms": round(statistics.median(s[k] for s in stages), 4) for k in stages[0]},
                        **measure(index, couriers, lat, lon, radius, repeats),
                    }
                )

    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "benchmark.csv", rows)
    _write_csv(out / "index_build.csv", builds)
    (out / "environment.txt").write_text(
        f"Python {platform.python_version()}\n{platform.platform()}\n{platform.processor() or platform.machine()}\n"
        f"repetições: {repeats}, semente: {seed}, σ = {SIGMA_M.default} m\n",
        encoding="utf-8",
    )
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _mean(rows, key, **where):
    return statistics.fmean(r[key] for r in rows if all(r[k] == v for k, v in where.items()))


def charts(rows: list[dict], out: Path) -> None:
    for radius in (0.5, 2):
        svg = line_chart(
            f"Tempo de consulta x tamanho da frota (raio de {str(radius).replace('.', ',')} km)",
            "entregadores na frota (N)",
            "tempo (ms, escala log)",
            FLEET_SIZES,
            {
                "Trie + vizinhança": [_mean(rows, "indexed_ms", n=n, radius_km=radius) for n in FLEET_SIZES],
                "Varredura linear": [_mean(rows, "linear_ms", n=n, radius_km=radius) for n in FLEET_SIZES],
                "Linear + caixa": [_mean(rows, "linear_bbox_ms", n=n, radius_km=radius) for n in FLEET_SIZES],
            },
            log_y=True,
        )
        (out / f"time_vs_n_r{str(radius).replace('.', '_')}.svg").write_text(svg, encoding="utf-8")

    n = 10_000
    svg = stacked_bars(
        f"Tempo por etapa da consulta (N = {n:,})".replace(",", "."),
        "raio de atendimento (km)",
        "tempo (ms)",
        [str(r).replace(".", ",") for r in RADII_KM],
        {
            "Geohash + vizinhas": [_mean(rows, "encode_ms", n=n, radius_km=r) for r in RADII_KM],
            "Busca na Trie": [_mean(rows, "trie_ms", n=n, radius_km=r) for r in RADII_KM],
            "Filtro (caixa + Haversine)": [_mean(rows, "filter_ms", n=n, radius_km=r) for r in RADII_KM],
        },
    )
    (out / "stages.svg").write_text(svg, encoding="utf-8")

    svg = line_chart(
        "Fração da frota examinada pela Trie",
        "raio de atendimento (km)",
        "candidatos / N (%)",
        RADII_KM,
        {
            label: [100 * _mean(rows, "candidates", n=n, radius_km=r, restaurant=label) / n for r in RADII_KM]
            for label in REFERENCE_RESTAURANTS.values()
        },
    )
    (out / "candidates_fraction.svg").write_text(svg, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "results")
    args = parser.parse_args()
    rows = run(args.repeats, args.seed, args.out)
    charts(rows, args.out)
    print(f"Resultados em {args.out}")


if __name__ == "__main__":
    main()
