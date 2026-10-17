# Entregadores próximos: Geohash + Trie compacta

Trabalho prático 1 de Algoritmos 2 (DCC207, UFMG).

Motor de busca de entregadores para restaurantes de Belo Horizonte. Cada entregador é
codificado em Geohash (8 caracteres) e indexado numa Trie compacta. Para atender um pedido, o
sistema codifica a posição do restaurante, busca o prefixo da célula e de suas 8 vizinhas e,
por fim, filtra os candidatos pelo raio de atendimento com a fórmula de Haversine.

A frota é sintética: as posições seguem uma distribuição normal em torno dos bares da base e
depois são projetadas na rua mais próxima da malha viária do OpenStreetMap.

O relatório está em [`docs/report.md`](docs/report.md).

## Como executar

Requer Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

Abra <http://127.0.0.1:8050>.

Na primeira execução, a malha viária de BH é baixada do OpenStreetMap e salva em
`data/cache/`. Isso leva de 2 a 4 minutos. Nas execuções seguintes, o app sobe em cerca de
10 segundos e não precisa de rede, exceto para as imagens do mapa.

### Com Docker

```bash
docker build -t geohash-courier-finder .
docker run --rm -p 8050:8050 geohash-courier-finder
```

O grafo é baixado durante o build, então o container já sobe pronto.

## Como usar

1. Informe a quantidade de entregadores e clique em **Gerar entregadores**. A semente é
   opcional; com a mesma semente, a frota é sempre a mesma.
2. Busque um restaurante pelo nome ou pelo endereço (ex.: "mercado central" ou
   "augusto de lima 744").
3. Ajuste o raio de atendimento. O mapa, as métricas e a tabela são atualizados na hora.

No mapa:

| Marcador | Significado |
|---|---|
| Vermelho, com borda branca | Entregador dentro do raio |
| Cinza-escuro | Candidato devolvido pela Trie, mas fora do raio |
| Cinza-claro, pequeno | Entregador fora das células pesquisadas |
| Retângulos azuis | As 9 células Geohash pesquisadas (a central em destaque) |

## Testes

```bash
pip install -r requirements-dev.txt
pytest -m "not graph"      # sem precisar do grafo
pytest                     # inclui os testes da projeção viária (exige data/cache/)
```

## Experimentos

```bash
python -m scripts.benchmark
```

Gera em `docs/results/` os tempos de consulta (busca indexada, varredura linear e varredura
linear com pré-filtro de caixa) para N = 1.000 a 20.000 e raios de 0,5 a 5 km, além dos
gráficos em SVG usados no relatório.

## Estrutura

```
core/          Geohash, Trie compacta, geometria e índice da frota (só biblioteca padrão)
catalog/       carga e busca textual da base de restaurantes
simulation/    geração da frota e projeção na malha viária
app/           interface (Dash + dash-leaflet)
scripts/       pré-processamento da base, benchmark e gráficos
tests/         testes automatizados (pytest)
data/          base de restaurantes (e o cache do grafo, fora do git)
docs/          relatório, decisões de projeto e resultados
```

## Dados

`data/restaurants.csv` contém os 20.859 estabelecimentos de alimentação (CNAE 5611-2) do
[cadastro de Atividades Econômicas da PBH](https://dados.pbh.gov.br/dataset/atividade-economica),
versão de setembro de 2026. As coordenadas originais estão em SIRGAS 2000 / UTM 23S e foram
convertidas para latitude e longitude por `scripts/build_restaurants.py`:

```bash
python scripts/build_restaurants.py 20260901_atividade_economica.csv
```

Os bares (CNAE 5611204 e 5611205, 4.715 estabelecimentos) são os centros da distribuição dos
entregadores.

## Dependências

As estruturas e os algoritmos centrais (Geohash, vizinhança, Trie, Haversine, conversão UTM e
projeção na rua) foram implementados sem bibliotecas externas. O projeto usa diretamente apenas:

| Biblioteca | Uso |
|---|---|
| `dash` | aplicação web |
| `dash-leaflet` | mapa interativo |
| `osmnx` | download da malha viária e escolha da aresta mais próxima |

`pytest` e `ruff` são usados só no desenvolvimento.
