FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0

WORKDIR /srv/app

COPY requirements.txt .
RUN pip install -r requirements.txt

# O grafo viário é baixado durante o build, numa camada própria
COPY config.py ./
COPY core/ core/
COPY simulation/ simulation/
RUN python -m simulation.road_network

COPY data/restaurants.csv data/
COPY catalog/ catalog/
COPY app/ app/

RUN useradd --create-home appuser && chown -R appuser /srv/app
USER appuser

EXPOSE 8050
CMD ["python", "-m", "app.main"]
