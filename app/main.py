"""Ponto de entrada: carrega a base e a malha viária, cria o app e sobe o servidor.

Uso: python -m app.main
"""

import os
from pathlib import Path

from dash import Dash

from app import callbacks, layout
from catalog.restaurants import RestaurantCatalog
from config import BAR_CATEGORIES, RESTAURANTS_CSV

INDEX_STRING = """<!DOCTYPE html>
<html lang="pt-BR">
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""


def create_app(network=None) -> Dash:
    catalog = RestaurantCatalog.load(RESTAURANTS_CSV)
    app = Dash(
        __name__,
        title="Entregadores próximos · BH",
        update_title=None,
        assets_folder=str(Path(__file__).parent / "assets"),
    )
    app.index_string = INDEX_STRING
    bars = len(catalog.with_categories(BAR_CATEGORIES))
    app.layout = layout.build(f"{callbacks.fmt(len(catalog))} restaurantes · {callbacks.fmt(bars)} bares")
    callbacks.register(app, catalog, network, callbacks.FleetState())
    return app


def main() -> None:
    # importado aqui para que create_app possa ser usado sem o osmnx (ex.: testes)
    from simulation.road_network import RoadNetwork

    print("Carregando a malha viária…")
    network = RoadNetwork.load()
    app = create_app(network)
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8050")), debug=False)


if __name__ == "__main__":
    main()
