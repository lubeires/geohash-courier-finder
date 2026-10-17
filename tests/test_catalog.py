import time

import pytest

from catalog.restaurants import Restaurant, RestaurantCatalog, display_case, normalize
from config import BAR_CATEGORIES, RESTAURANTS_CSV


@pytest.fixture(scope="module")
def catalog():
    return RestaurantCatalog.load(RESTAURANTS_CSV)


def make(id_, name, street_type="RUA", street="ALAGOAS", number="10", neighborhood="SAVASSI"):
    return Restaurant(id_, "bar", name, name, street_type, street, number, "", neighborhood, -19.93, -43.93)


def test_load(catalog):
    assert len(catalog) == 20_859
    assert len(catalog.with_categories(BAR_CATEGORIES)) == 4715
    restaurant = catalog.get("114942")
    assert restaurant.name == "BAR MERCADO CENTRAL LTDA"
    assert restaurant.lat == pytest.approx(-19.923022)


def test_normalize():
    assert normalize("Av. Augusto de Lima, 744") == "av augusto de lima 744"
    assert normalize("  PÇA. São João  ") == "pca sao joao"


def test_display_case():
    assert display_case("BAR DO FABIO") == "Bar do Fabio"
    assert display_case("DE MINAS BAR") == "De Minas Bar"
    assert display_case("D.J. LANCHES 8ZH7") == "D.J. Lanches 8ZH7"


def test_address_and_label():
    r = make("1", "CHIC TACIO LTDA", "AVE", "AUGUSTO DE LIMA", "744", "CENTRO")
    assert r.address == "Av. Augusto de Lima, 744"
    assert r.label == "Chic Tacio Ltda — Av. Augusto de Lima, 744 · Centro"
    assert make("2", "X", "VIA").address.startswith("Via ")
    assert make("3", "X", "XYZ").address.startswith("Xyz ")


def test_search_mercado_central(catalog):
    ids = {r.id for r in catalog.search("mercado central")}
    assert {"113517", "114942"} <= ids


def test_search_by_address(catalog):
    results = catalog.search("augusto de lima 744")
    assert len(results) == 20
    assert all(r.street_name == "AUGUSTO DE LIMA" and r.number == "744" for r in results)


def test_search_ignores_accents_and_case(catalog):
    results = catalog.search("Lanchonete dos Jornalistas")
    assert results
    assert results == catalog.search("lanchonete dos jornalistas")
    assert catalog.search("savassí")


def test_search_short_query(catalog):
    assert catalog.search("b") == []
    assert catalog.search("  ") == []


def test_search_ranking():
    catalog = RestaurantCatalog(
        [make("1", "ZECA BAR"), make("2", "BAR DO ZE"), make("3", "BARRACA"), make("4", "AMIGOS DO BAR")]
    )
    assert [r.id for r in catalog.search("bar")] == ["2", "3", "4", "1"]


def test_search_is_fast(catalog):
    start = time.perf_counter()
    catalog.search("rua")
    assert time.perf_counter() - start < 0.1
