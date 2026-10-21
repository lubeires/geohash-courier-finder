"""Callbacks da interface. A lógica está no core e na simulação; aqui só se monta a resposta."""

import statistics
from collections.abc import Iterable

import dash_leaflet as dl
from dash import ALL, Dash, Input, Output, State, ctx, html, no_update
from dash.exceptions import PreventUpdate

from app.layout import EMPTY_COLLECTION
from catalog.restaurants import Restaurant, RestaurantCatalog, display_case, normalize
from config import BAR_CATEGORIES, FLEET_SIZE, MAX_SUGGESTIONS, MIN_QUERY_LENGTH, SIGMA_M, SPEED_KMH, Param
from core.fleet_index import Courier, FleetIndex, QueryResult
from core.geohash import decode_bbox
from core.geometry import bbox_around
from simulation.generator import generate_fleet


class FleetState:
    """Frota atual do servidor. O app é pensado para um usuário por vez."""

    def __init__(self) -> None:
        self.index: FleetIndex | None = None
        self.generation = 0

    def replace(self, index: FleetIndex) -> int:
        # a frota anterior (Trie inclusive) é descartada junto com a referência
        self.index = index
        self.generation += 1
        return self.generation

    def get(self, generation: int | None) -> FleetIndex | None:
        return self.index if generation == self.generation else None


# Formatação


def fmt(value: float, decimals: int = 0) -> str:
    """Número no padrão brasileiro: 1.234,5"""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def validation_error(value, param: Param, integer: bool = False) -> str:
    if value is None:
        return f"Informe um valor entre {fmt(param.minimum, 1 if param.minimum % 1 else 0)} e {fmt(param.maximum)}."
    if integer and value != int(value):
        return "Informe um número inteiro."
    if not param.minimum <= value <= param.maximum:
        return f"O valor deve estar entre {fmt(param.minimum, 1 if param.minimum % 1 else 0)} e {fmt(param.maximum)}."
    return ""


def seed_error(value) -> str:
    if value is None:
        return ""
    return "" if value >= 0 and value == int(value) else "A semente deve ser um inteiro ≥ 0."


# Camadas do mapa

DENSE_THRESHOLD = 1500


def _point(lat: float, lon: float, properties: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
        "properties": properties,
    }


def fleet_geojson(couriers: Iterable[Courier]) -> dict:
    return {"type": "FeatureCollection", "features": [_point(c.lat, c.lon, {}) for c in couriers]}


def candidates_geojson(result: QueryResult) -> dict:
    features = [_point(c.lat, c.lon, {"accepted": False, "tip": f"{c.id} · fora do raio"}) for c in result.rejected]
    # com muitos aceitos, pinos menores e sem borda (senão as bordas brancas viram uma mancha)
    dense = len(result.accepted) > DENSE_THRESHOLD
    # do mais distante para o mais próximo, para o mais próximo ficar por cima
    for courier, distance, eta in reversed(result.accepted):
        tip = f"{courier.id} · {fmt(distance, 2)} km · {fmt(eta, 1)} min"
        features.append(_point(courier.lat, courier.lon, {"accepted": True, "dense": dense, "tip": tip}))
    return {"type": "FeatureCollection", "features": features}


def restaurant_layers(restaurant: Restaurant, radius_km: float) -> list:
    position = [restaurant.lat, restaurant.lon]
    return [
        dl.Circle(
            center=position,
            radius=radius_km * 1000,
            color="#c62828",
            weight=2,
            fillColor="#c62828",
            fillOpacity=0.08,
            interactive=False,
        ),
        dl.Marker(
            position=position,
            icon={"iconUrl": "/assets/restaurant.svg", "iconSize": [34, 44], "iconAnchor": [17, 43]},
            zIndexOffset=1000,
            children=dl.Tooltip(f"{restaurant.display_name} · {restaurant.address}", direction="top", offset=[0, -40]),
        ),
    ]


def cell_layers(cells: list[str]) -> list:
    layers = []
    for i, cell in enumerate(cells):
        south, north, west, east = decode_bbox(cell)
        is_center = i == 0
        layers.append(
            dl.Rectangle(
                bounds=[[south, west], [north, east]],
                color="#1d4ed8",
                weight=2.5 if is_center else 1.5,
                dashArray=None if is_center else "6 4",
                fill=False,
                interactive=False,
            )
        )
        # rótulo no canto noroeste, para não cobrir o restaurante
        layers.append(
            dl.DivMarker(
                position=[north, west],
                iconOptions={
                    "className": "cell-label cell-label-center" if is_center else "cell-label",
                    "html": f"<span>{cell}</span>",
                    "iconSize": [0, 0],
                    "iconAnchor": [-4, -4],
                },
                interactive=False,
            )
        )
    return layers


# Métricas e tabela


def notice(text: str) -> html.Div:
    return html.Div(text, className="notice")


def intro(has_fleet: bool) -> html.Div:
    steps = [
        ("Gere a frota", "informe quantos entregadores simular e clique em Gerar entregadores."),
        ("Escolha um restaurante", "busque pelo nome ou pelo endereço."),
        ("Ajuste o raio", "o mapa, as métricas e a tabela são atualizados na hora."),
    ]
    items = [
        html.Li([html.Strong(title), f": {text}"], className="done" if i == 0 and has_fleet else None)
        for i, (title, text) in enumerate(steps)
    ]
    return html.Div([html.H2("Como usar"), html.Ol(items)], className="notice notice-intro")


def _card(label: str, value: str, detail: str = "") -> html.Div:
    return html.Div(
        [
            html.P(label, className="card-label"),
            html.P(value, className="card-value"),
            html.P(detail, className="card-detail"),
        ],
        className="card",
    )


def metrics_cards(result: QueryResult, fleet_size: int, speed_kmh: float) -> list:
    accepted = result.accepted
    t = result.timings_ms
    timing = _card(
        "Tempo da consulta",
        f"{fmt(t['total'], 2)} ms",
        f"Geohash {fmt(t['encode'], 2)} · Trie {fmt(t['trie'], 2)} · filtro {fmt(t['filter'], 2)} ms",
    )
    found = _card(
        "Dentro do raio",
        fmt(len(accepted)),
        f"{fmt(result.candidates_count)} candidatos na Trie · {fmt(fleet_size)} na frota",
    )
    cells = _card("Busca na Trie", f"precisão {result.precision}", f"{len(result.cells)} células Geohash")
    if not accepted:
        return [
            found,
            _card("Mais próximo", "—"),
            _card("Distância média", "—"),
            _card("Tempo médio", "—"),
            cells,
            timing,
        ]

    nearest = accepted[0]
    distances = [m.distance_km for m in accepted]
    return [
        found,
        _card(
            "Mais próximo", f"{fmt(nearest.distance_km, 2)} km", f"{nearest.courier.id} · {fmt(nearest.eta_min, 1)} min"
        ),
        _card(
            "Distância média",
            f"{fmt(statistics.fmean(distances), 2)} km",
            f"mín. {fmt(distances[0], 2)} · máx. {fmt(distances[-1], 2)} km",
        ),
        _card(
            "Tempo médio", f"{fmt(statistics.fmean(m.eta_min for m in accepted), 1)} min", f"a {fmt(speed_kmh)} km/h"
        ),
        cells,
        timing,
    ]


def results_table(result: QueryResult, radius_km: float) -> list:
    if not result.accepted:
        return [notice(f"Nenhum entregador a até {fmt(radius_km, 1)} km. Aumente o raio ou gere mais entregadores.")]
    rows = [
        html.Tr(
            [
                html.Td(str(i), className="num"),
                html.Td(m.courier.id, className="mono"),
                html.Td(fmt(m.distance_km, 2), className="num"),
                html.Td(fmt(m.eta_min, 1), className="num"),
                html.Td(m.courier.geohash, className="mono"),
            ]
        )
        for i, m in enumerate(result.accepted, start=1)
    ]
    header = html.Tr(
        [
            html.Th("#", scope="col", className="num"),
            html.Th("Entregador", scope="col"),
            html.Th("Distância (km)", scope="col", className="num"),
            html.Th("Tempo estimado (min)", scope="col", className="num"),
            html.Th("Geohash", scope="col"),
        ]
    )
    title = f"Entregadores dentro do raio ({fmt(len(rows))})"
    table = html.Table(
        [html.Caption(title), html.Thead(header), html.Tbody(rows)],
        className="results-table",
    )
    return [html.Div([html.H2(title), html.Div(table, className="table-scroll", tabIndex=0)], className="results")]


# Registro dos callbacks


def register(app: Dash, catalog: RestaurantCatalog, network, state: FleetState) -> None:
    centers = [(r.id, r.lat, r.lon) for r in catalog.with_categories(BAR_CATEGORIES)]
    snap = network.snap if network is not None else None

    @app.callback(Output("restaurant-suggestions", "children"), Input("restaurant-query", "value"))
    def suggest_restaurants(query):
        if not query or len(normalize(query)) < MIN_QUERY_LENGTH:
            return []
        found = catalog.search(query, MAX_SUGGESTIONS, MIN_QUERY_LENGTH)
        if not found:
            return html.P("Nenhum restaurante encontrado.", className="field-hint")
        return [
            html.Button(
                [html.Strong(r.display_name), html.Span(f"{r.address} · {display_case(r.neighborhood)}")],
                id={"type": "suggestion", "id": r.id},
                className="suggestion",
            )
            for r in found
        ]

    @app.callback(
        Output("selected-restaurant", "data"),
        Output("restaurant-query", "value"),
        Input({"type": "suggestion", "id": ALL}, "n_clicks"),
        Input("clear-restaurant", "n_clicks"),
        prevent_initial_call=True,
    )
    def select_restaurant(suggestion_clicks, _):
        # a lista de sugestões é recriada a cada busca, o que também dispara este callback
        if not ctx.triggered or not ctx.triggered[0]["value"]:
            raise PreventUpdate
        if ctx.triggered_id == "clear-restaurant":
            return None, no_update
        return ctx.triggered_id["id"], ""

    @app.callback(
        Output("selected-card", "className"),
        Output("selected-name", "children"),
        Output("selected-address", "children"),
        Input("selected-restaurant", "data"),
    )
    def show_selected(restaurant_id):
        restaurant = catalog.get(restaurant_id) if restaurant_id else None
        if restaurant is None:
            return "selected-card hidden", "", ""
        return (
            "selected-card",
            restaurant.display_name,
            f"{restaurant.address} · {display_case(restaurant.neighborhood)}",
        )

    @app.callback(
        Output("generate-btn", "disabled"),
        Output("fleet-size-error", "children"),
        Output("sigma-error", "children"),
        Output("seed-error", "children"),
        Output("speed-error", "children"),
        Input("fleet-size", "value"),
        Input("sigma", "value"),
        Input("seed", "value"),
        Input("speed", "value"),
    )
    def validate_inputs(fleet_size, sigma, seed, speed):
        errors = (
            validation_error(fleet_size, FLEET_SIZE, integer=True),
            validation_error(sigma, SIGMA_M),
            seed_error(seed),
        )
        return any(errors), *errors, validation_error(speed, SPEED_KMH)

    @app.callback(
        Output("fleet-meta", "data"),
        Output("fleet-layer", "data"),
        Output("fleet-status", "children"),
        Input("generate-btn", "n_clicks"),
        State("fleet-size", "value"),
        State("sigma", "value"),
        State("seed", "value"),
        prevent_initial_call=True,
        running=[
            (Output("fleet-fieldset", "disabled"), True, False),
            (Output("generate-btn", "children"), "Gerando…", "Gerar entregadores"),
        ],
    )
    def generate(_, fleet_size, sigma, seed):
        if (
            validation_error(fleet_size, FLEET_SIZE, integer=True)
            or validation_error(sigma, SIGMA_M)
            or seed_error(seed)
        ):
            raise PreventUpdate
        fleet = generate_fleet(
            centers, int(fleet_size), float(sigma), seed=None if seed is None else int(seed), snap=snap
        )
        generation = state.replace(FleetIndex(fleet.couriers))
        status = (
            f"{fmt(len(fleet.couriers))} entregadores gerados em {fmt(fleet.timings_ms['total'] / 1000, 1)} s "
            f"· semente {fleet.seed}"
        )
        meta = {"generation": generation, "size": len(fleet.couriers), "seed": fleet.seed}
        return meta, fleet_geojson(fleet.couriers), status

    @app.callback(
        Output("candidates-layer", "data"),
        Output("query-layer", "children"),
        Output("query-meta", "data"),
        Output("metrics", "children"),
        Output("results", "children"),
        Output("map", "viewport"),
        Input("selected-restaurant", "data"),
        Input("radius", "value"),
        Input("speed", "value"),
        Input("fleet-meta", "data"),
    )
    def run_query(restaurant_id, radius_km, speed_kmh, fleet_meta):
        restaurant = catalog.get(restaurant_id) if restaurant_id else None
        index = state.get(fleet_meta["generation"]) if fleet_meta else None

        if restaurant is None:
            return EMPTY_COLLECTION, [], None, [intro(index is not None)], [], no_update

        viewport = no_update
        if ctx.triggered_id in ("selected-restaurant", "radius"):
            (south, west), (north, east) = bbox_around(restaurant.lat, restaurant.lon, radius_km * 1.15)
            viewport = {"bounds": [[south, west], [north, east]], "transition": "fitBounds"}
        layers = restaurant_layers(restaurant, radius_km)

        if index is None:
            return EMPTY_COLLECTION, layers, None, [intro(False)], [], viewport
        if validation_error(speed_kmh, SPEED_KMH):
            return EMPTY_COLLECTION, layers, None, [notice("Corrija a velocidade média.")], [], viewport

        result = index.query(restaurant.lat, restaurant.lon, radius_km, speed_kmh)
        return (
            candidates_geojson(result),
            layers,
            {"cells": list(result.cells)},
            metrics_cards(result, len(index), speed_kmh),
            results_table(result, radius_km),
            viewport,
        )

    @app.callback(Output("radius-value", "children"), Input("radius", "value"))
    def show_radius(radius_km):
        return f"{fmt(radius_km, 1)} km"

    @app.callback(
        Output("cells-layer", "children"),
        Input("show-cells", "value"),
        Input("query-meta", "data"),
    )
    def draw_cells(show, query_meta):
        if not show or not query_meta:
            return []
        return cell_layers(query_meta["cells"])
