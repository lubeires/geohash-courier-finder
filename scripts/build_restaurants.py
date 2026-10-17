"""Gera data/restaurants.csv a partir do CSV de Atividades Econômicas da PBH.

Mantém apenas os estabelecimentos de alimentação (CNAE 5611-2) e converte a
coluna GEOMETRIA, em SIRGAS 2000 / UTM 23S (EPSG:31983), para latitude e
longitude.

Uso:
    python scripts/build_restaurants.py <atividade_economica.csv> [saida.csv]

Fonte: https://dados.pbh.gov.br/dataset/atividade-economica
"""

import csv
import math
import sys
from pathlib import Path

CATEGORIES = {
    "5611201": "restaurant",
    "5611203": "snack_bar",
    "5611204": "bar",
    "5611205": "bar_entertainment",
}

# Elipsoide GRS80 (SIRGAS 2000) e parâmetros da zona UTM 23 Sul
SEMI_MAJOR_AXIS = 6378137.0
FLATTENING = 1 / 298.257222101
SCALE_FACTOR = 0.9996
FALSE_EASTING = 500_000.0
FALSE_NORTHING = 10_000_000.0
CENTRAL_MERIDIAN = -45.0

OUTPUT_FIELDS = [
    "id",
    "category",
    "name",
    "legal_name",
    "street_type",
    "street_name",
    "number",
    "complement",
    "neighborhood",
    "lat",
    "lon",
]


def utm_to_latlon(easting: float, northing: float) -> tuple[float, float]:
    """Converte coordenadas UTM 23S para (lat, lon) em graus.

    Usa a série inversa de Krüger (expansão em n até a 6ª ordem), com erro
    submilimétrico dentro da zona.
    """
    n = FLATTENING / (2 - FLATTENING)
    a_hat = SEMI_MAJOR_AXIS / (1 + n) * (1 + n**2 / 4 + n**4 / 64 + n**6 / 256)
    beta = (
        n / 2 - 2 * n**2 / 3 + 37 * n**3 / 96 - n**4 / 360 - 81 * n**5 / 512 + 96199 * n**6 / 604800,
        n**2 / 48 + n**3 / 15 - 437 * n**4 / 1440 + 46 * n**5 / 105 - 1118711 * n**6 / 3870720,
        17 * n**3 / 480 - 37 * n**4 / 840 - 209 * n**5 / 4480 + 5569 * n**6 / 90720,
        4397 * n**4 / 161280 - 11 * n**5 / 504 - 830251 * n**6 / 7257600,
        4583 * n**5 / 161280 - 108847 * n**6 / 3991680,
        20648693 * n**6 / 638668800,
    )

    xi = (northing - FALSE_NORTHING) / (SCALE_FACTOR * a_hat)
    eta = (easting - FALSE_EASTING) / (SCALE_FACTOR * a_hat)

    xi_p = xi - sum(b * math.sin(2 * j * xi) * math.cosh(2 * j * eta) for j, b in enumerate(beta, 1))
    eta_p = eta - sum(b * math.cos(2 * j * xi) * math.sinh(2 * j * eta) for j, b in enumerate(beta, 1))

    # Latitude conforme -> geodésica por iteração de Newton (converge em poucas iterações)
    tau_p = math.sin(xi_p) / math.hypot(math.sinh(eta_p), math.cos(xi_p))
    e = math.sqrt(FLATTENING * (2 - FLATTENING))
    tau = tau_p
    for _ in range(10):
        sigma = math.sinh(e * math.atanh(e * tau / math.sqrt(1 + tau**2)))
        tau_i = tau * math.sqrt(1 + sigma**2) - sigma * math.sqrt(1 + tau**2)
        delta = (
            (tau_p - tau_i) / math.sqrt(1 + tau_i**2) * (1 + (1 - e**2) * tau**2) / ((1 - e**2) * math.sqrt(1 + tau**2))
        )
        tau += delta
        if abs(delta) < 1e-12:
            break

    lat = math.degrees(math.atan(tau))
    lon = CENTRAL_MERIDIAN + math.degrees(math.atan2(math.sinh(eta_p), math.cos(xi_p)))
    return lat, lon


def parse_point(wkt: str) -> tuple[float, float]:
    """Extrai (x, y) de uma string 'POINT (x y)'."""
    x, y = wkt[wkt.index("(") + 1 : wkt.index(")")].split()
    return float(x), float(y)


def build(source: Path, target: Path) -> int:
    count = 0
    with (
        source.open(encoding="utf-8", newline="") as src,
        target.open("w", encoding="utf-8", newline="") as dst,
    ):
        writer = csv.DictWriter(dst, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in csv.DictReader(src, delimiter=";"):
            category = CATEGORIES.get(row["CNAE_PRINCIPAL"])
            if category is None or not row["GEOMETRIA"].strip():
                continue
            lat, lon = utm_to_latlon(*parse_point(row["GEOMETRIA"]))
            legal_name = row["NOME"].strip()
            writer.writerow(
                {
                    "id": row["ID_ATIV_ECON_ESTABELECIMENTO"],
                    "category": category,
                    "name": row["NOME_FANTASIA"].strip() or legal_name,
                    "legal_name": legal_name,
                    "street_type": row["DESC_LOGRADOURO"].strip(),
                    "street_name": row["NOME_LOGRADOURO"].strip(),
                    "number": row["NUMERO_IMOVEL"].strip(),
                    "complement": row["COMPLEMENTO"].strip(),
                    "neighborhood": row["NOME_BAIRRO"].strip(),
                    "lat": f"{lat:.6f}",
                    "lon": f"{lon:.6f}",
                }
            )
            count += 1
    return count


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    source = Path(sys.argv[1])
    target = Path(sys.argv[2]) if len(sys.argv) == 3 else Path(__file__).parent.parent / "data" / "restaurants.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"{build(source, target)} estabelecimentos gravados em {target}")


if __name__ == "__main__":
    main()
