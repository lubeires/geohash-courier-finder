from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent
RESTAURANTS_CSV = ROOT / "data" / "restaurants.csv"
CACHE_DIR = ROOT / "data" / "cache"
GRAPH_PATH = CACHE_DIR / "bh_drive.graphml"
PLACE_QUERY = "Belo Horizonte, Minas Gerais, Brazil"

BH_CENTER = (-19.9191, -43.9386)

# Categorias usadas como centros da distribuição dos entregadores
BAR_CATEGORIES = frozenset({"bar", "bar_entertainment"})


class Param(NamedTuple):
    default: float
    minimum: float
    maximum: float
    step: float


FLEET_SIZE = Param(1000, 1, 20_000, 1)
RADIUS_KM = Param(2.0, 0.1, 10.0, 0.1)
SIGMA_M = Param(400, 50, 2000, 10)
SPEED_KMH = Param(20, 5, 60, 1)

MAX_SUGGESTIONS = 20
MIN_QUERY_LENGTH = 2
