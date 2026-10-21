"""Estrutura da página: painel de controles, mapa, métricas e tabela."""

import dash_leaflet as dl
from dash import dcc, html

from config import BH_CENTER, FLEET_SIZE, RADIUS_KM, SIGMA_M, SPEED_KMH, Param

EMPTY_COLLECTION = {"type": "FeatureCollection", "features": []}

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'


def _number_input(input_id: str, param: Param, **kwargs) -> dcc.Input:
    return dcc.Input(
        id=input_id,
        type="number",
        value=kwargs.pop("value", param.default),
        min=param.minimum,
        max=param.maximum,
        step=param.step,
        debounce=True,
        className="input",
        **kwargs,
    )


def _field(label: str, control, control_id: str, error_id: str | None = None, hint: str | None = None) -> html.Div:
    children = [html.Label(label, htmlFor=control_id, className="field-label"), control]
    if hint:
        children.append(html.P(hint, className="field-hint"))
    if error_id:
        children.append(html.P(id=error_id, className="field-error", role="alert"))
    return html.Div(children, className="field")


def _step(number: int, title: str) -> html.H2:
    return html.H2([html.Span(str(number), className="step-number", **{"aria-hidden": "true"}), title])


def _panel() -> html.Aside:
    fleet = html.Fieldset(
        [
            html.Legend(_step(1, "Frota de entregadores")),
            _field(
                "Quantidade de entregadores (N)",
                _number_input("fleet-size", FLEET_SIZE),
                "fleet-size",
                error_id="fleet-size-error",
            ),
            html.Div(
                [
                    _field("Dispersão σ (m)", _number_input("sigma", SIGMA_M), "sigma", error_id="sigma-error"),
                    _field(
                        "Semente",
                        dcc.Input(
                            id="seed",
                            type="number",
                            min=0,
                            step=1,
                            placeholder="auto",
                            debounce=True,
                            className="input",
                        ),
                        "seed",
                        error_id="seed-error",
                    ),
                ],
                className="field-row",
            ),
            html.Button("Gerar entregadores", id="generate-btn", className="button", n_clicks=0),
            dcc.Loading(html.P(id="fleet-status", className="status", **{"aria-live": "polite"}), type="dot"),
        ],
        id="fleet-fieldset",
        className="panel-section",
    )

    restaurant = html.Section(
        [
            _step(2, "Restaurante"),
            html.Div(
                [
                    html.Div(
                        [html.Strong(id="selected-name"), html.Span(id="selected-address")],
                        className="selected-text",
                    ),
                    html.Button("×", id="clear-restaurant", className="clear-button", title="Limpar seleção"),
                ],
                id="selected-card",
                className="selected-card hidden",
                **{"aria-live": "polite"},
            ),
            _field(
                "Buscar por nome ou endereço",
                dcc.Input(
                    id="restaurant-query",
                    type="search",
                    placeholder="Ex.: Mercado Central",
                    debounce=0.25,
                    autoComplete="off",
                    className="input",
                ),
                "restaurant-query",
                hint="Digite ao menos 2 letras.",
            ),
            html.Div(id="restaurant-suggestions", className="suggestions"),
        ],
        className="panel-section",
    )

    radius = html.Section(
        [
            _step(3, "Raio de atendimento"),
            html.Div(
                [
                    html.Label("Distância máxima", htmlFor="radius", className="field-label"),
                    html.Output(id="radius-value", className="value-badge", htmlFor="radius"),
                ],
                className="label-row",
            ),
            dcc.Slider(
                id="radius",
                min=RADIUS_KM.minimum,
                max=RADIUS_KM.maximum,
                step=RADIUS_KM.step,
                value=RADIUS_KM.default,
                marks={0.1: "0,1", 2: "2", 4: "4", 6: "6", 8: "8", 10: "10"},
                updatemode="mouseup",
            ),
        ],
        className="panel-section",
    )

    eta = html.Section(
        [
            _step(4, "Tempo estimado"),
            _field(
                "Velocidade média (km/h)",
                _number_input("speed", SPEED_KMH),
                "speed",
                error_id="speed-error",
            ),
            html.Details(
                [
                    html.Summary("Como o tempo é calculado"),
                    html.P(
                        "Tempo = distância em linha reta (Haversine) ÷ velocidade média. É uma estimativa "
                        "otimista: o trajeto real pelas ruas é mais longo."
                    ),
                ],
                className="help",
            ),
        ],
        className="panel-section",
    )

    return html.Aside([fleet, restaurant, radius, eta], className="panel")


def _legend() -> html.Div:
    return html.Div(
        html.Ul(
            [
                html.Li([html.Span(html.Img(src="/assets/restaurant.svg", alt=""), className="swatch"), "Restaurante"]),
                html.Li([html.Span(className="swatch swatch-accepted"), "Dentro do raio"]),
                html.Li([html.Span(className="swatch swatch-rejected"), "Candidato fora do raio"]),
                html.Li([html.Span(className="swatch swatch-other"), "Fora das células pesquisadas"]),
                html.Li([html.Span(className="swatch swatch-radius"), "Raio de atendimento"]),
                html.Li([html.Span(className="swatch swatch-cell"), "Células Geohash pesquisadas"]),
            ]
        ),
        className="map-overlay map-legend",
        role="note",
        **{"aria-label": "Legenda do mapa"},
    )


def _map() -> html.Div:
    leaflet_map = dl.Map(
        id="map",
        center=BH_CENTER,
        zoom=12,
        preferCanvas=True,
        style={"height": "100%", "width": "100%"},
        children=[
            dl.TileLayer(url=TILE_URL, attribution=TILE_ATTRIBUTION, maxZoom=19),
            dl.Pane(
                name="fleet",
                children=dl.GeoJSON(
                    id="fleet-layer",
                    data=EMPTY_COLLECTION,
                    pointToLayer={"variable": "courierMap.fleetPoint"},
                    interactive=False,
                ),
            ),
            dl.Pane(
                name="candidates",
                children=dl.GeoJSON(
                    id="candidates-layer",
                    data=EMPTY_COLLECTION,
                    pointToLayer={"variable": "courierMap.candidatePoint"},
                ),
            ),
            dl.LayerGroup(id="cells-layer"),
            dl.LayerGroup(id="query-layer"),
            dl.ScaleControl(position="bottomleft", imperial=False),
        ],
    )
    toggle = html.Div(
        dcc.Checklist(
            id="show-cells",
            options=[{"label": "Mostrar células pesquisadas", "value": "cells"}],
            value=["cells"],
            inputStyle={"margin": 0},
        ),
        className="map-overlay map-toggle",
    )
    return html.Div([leaflet_map, toggle, _legend()], className="map-wrap")


def build(stats: str = "") -> html.Div:
    return html.Div(
        [
            html.Header(
                [
                    html.Img(src="/assets/restaurant.svg", alt="", className="brand-mark"),
                    html.Div(
                        [
                            html.H1("Entregadores próximos"),
                            html.P("Busca geoespacial com Geohash e Trie compacta · Belo Horizonte"),
                        ]
                    ),
                    html.P(stats, className="header-stats"),
                ],
                className="app-header",
            ),
            _panel(),
            html.Main(
                [
                    _map(),
                    html.Section(id="metrics", className="metrics", **{"aria-live": "polite"}),
                    html.Section(id="results", className="results-wrap"),
                ],
                className="main",
            ),
            dcc.Store(id="fleet-meta"),
            dcc.Store(id="selected-restaurant"),
            dcc.Store(id="query-meta"),
        ],
        className="app",
    )
