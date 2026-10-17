"""Base de restaurantes: carga do CSV e busca textual por nome ou endereço."""

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

STREET_TYPES = {
    "AVE": "Av.",
    "RUA": "R.",
    "PCA": "Pça.",
    "ROD": "Rod.",
    "ALA": "Al.",
    "BEC": "Bc.",
    "EST": "Est.",
    "TRV": "Tv.",
    "VDP": "Vd.",
    "VIA": "Via",
}

_LOWERCASE_WORDS = {"de", "da", "do", "das", "dos", "e"}
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def normalize(text: str) -> str:
    """Minúsculas, sem acentos e com toda pontuação trocada por um espaço."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NON_ALNUM.sub(" ", stripped.casefold()).strip()


def display_case(text: str) -> str:
    """'BAR DO FABIO' -> 'Bar do Fabio'. Palavras com dígitos ou pontos ficam como estão."""
    words = []
    for i, word in enumerate(text.split()):
        lower = word.lower()
        if any(c.isdigit() or c == "." for c in word):
            words.append(word)
        elif i > 0 and lower in _LOWERCASE_WORDS:
            words.append(lower)
        else:
            words.append(lower.capitalize())
    return " ".join(words)


@dataclass(frozen=True, slots=True)
class Restaurant:
    id: str
    category: str
    name: str
    legal_name: str
    street_type: str
    street_name: str
    number: str
    complement: str
    neighborhood: str
    lat: float
    lon: float

    @property
    def display_name(self) -> str:
        return display_case(self.name)

    @property
    def address(self) -> str:
        street_type = STREET_TYPES.get(self.street_type, self.street_type.title())
        return f"{street_type} {display_case(self.street_name)}, {self.number}"

    @property
    def label(self) -> str:
        return f"{self.display_name} — {self.address} · {display_case(self.neighborhood)}"


class RestaurantCatalog:
    def __init__(self, restaurants: list[Restaurant]) -> None:
        self._by_id = {r.id: r for r in restaurants}
        # Textos normalizados uma única vez, em ordem alfabética do nome
        entries = []
        for r in restaurants:
            haystack = " ".join((r.name, r.legal_name, r.address, r.street_name, r.number, r.neighborhood))
            entries.append((normalize(r.name), normalize(haystack), r))
        entries.sort(key=lambda e: (e[0], e[2].id))
        self._entries = entries

    @classmethod
    def load(cls, path: Path) -> "RestaurantCatalog":
        with path.open(encoding="utf-8", newline="") as f:
            restaurants = [
                Restaurant(
                    id=row["id"],
                    category=row["category"],
                    name=row["name"],
                    legal_name=row["legal_name"],
                    street_type=row["street_type"],
                    street_name=row["street_name"],
                    number=row["number"],
                    complement=row["complement"],
                    neighborhood=row["neighborhood"],
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                )
                for row in csv.DictReader(f)
            ]
        return cls(restaurants)

    def __len__(self) -> int:
        return len(self._by_id)

    def get(self, restaurant_id: str) -> Restaurant | None:
        return self._by_id.get(restaurant_id)

    def with_categories(self, categories: frozenset[str]) -> list[Restaurant]:
        return [r for r in self._by_id.values() if r.category in categories]

    def search(self, query: str, limit: int = 20, min_length: int = 2) -> list[Restaurant]:
        """Busca por substring. Primeiro os que começam pelo texto buscado, depois os demais."""
        q = normalize(query)
        if len(q) < min_length:
            return []
        starts, contains = [], []
        for name_key, haystack, restaurant in self._entries:
            if name_key.startswith(q):
                starts.append(restaurant)
                if len(starts) == limit:
                    break
            elif q in haystack:
                contains.append(restaurant)
        return (starts + contains)[:limit]
