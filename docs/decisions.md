# Registro de decisões

## Base de restaurantes

A base de bares não trazia coordenadas. Ela corresponde exatamente ao recorte dos CNAEs
5611201, 5611203, 5611204 e 5611205 do CSV de Atividades Econômicas da PBH de setembro de 2026
(20.859 linhas, mesma ordem e mesmo conteúdo). Usei o arquivo da PBH como fonte, já que ele
tem a coluna `GEOMETRIA`.

As coordenadas da PBH estão em SIRGAS 2000 / UTM 23S (EPSG:31983). A conversão para
latitude/longitude está em `scripts/build_restaurants.py` e usa a série inversa de Krüger.
Optei por não adicionar o `pyproj` como dependência só para isso. Conferi o resultado com o
`pyproj` para todos os pontos, e a maior diferença ficou abaixo de 1 µm.

O arquivo bruto (186 MB) não é versionado. O repositório guarda apenas `data/restaurants.csv`,
que tem 2,9 MB.

## Versões do Dash e do dash-leaflet

O dash-leaflet 1.1.3 não declara compatibilidade com o Dash 4, então testei antes num app mínimo:
camadas GeoJSON em panes separados com `pointToLayer` em JavaScript, marcador com ícone, círculo,
retângulo com rótulo permanente, `viewport` com `flyToBounds` e 20 mil pontos em canvas. Tudo
funcionou sem erros no console, então fiquei com o Dash 4.4.1.

## Malha viária

Grafo `drive` de Belo Horizonte pelo osmnx: 32.290 nós e 82.931 arestas, 36,5 MB em GraphML.
O download levou cerca de 2 min 40 s; a leitura do arquivo leva cerca de 7 s, e o
`nearest_edges` para 5.000 pontos, cerca de 1,7 s.

## Filtragem dos candidatos

Com raio de 2 km a busca usa precisão 5, e o bloco 3×3 de células cobre cerca de 14 × 15 km,
quase toda a área central da cidade. Na primeira versão, a consulta calculava o Haversine de
todos os candidatos e acabava mais lenta que a varredura linear.

Duas mudanças resolveram sem alterar o resultado:

- A Trie guarda o próprio objeto do entregador, e não o id, o que elimina uma busca no
  dicionário por candidato.
- Antes do Haversine, cada candidato passa por um teste contra a menor caixa que contém o
  círculo (Δφ = r/R e Δλ = asin(sin(r/R)/cos φ)). São duas comparações, e a maioria dos
  rejeitados para aí. Por isso os rejeitados não têm distância calculada.

Medição com 10 mil entregadores concentrados em torno de um ponto (σ ≈ 4 km) e raio de 2 km:
a consulta caiu de 42 ms para 12 ms. A divisão por etapa mostra que o custo restante é a coleta
na Trie, proporcional ao número de candidatos.

## Resultado dos experimentos

Comparei três formas de responder a mesma consulta (mediana de 30 execuções, frotas sem
projeção viária): a busca na Trie com as 9 células, a varredura linear com Haversine em todos os
entregadores e a varredura linear com o mesmo pré-filtro de caixa usado na busca indexada.

- A busca indexada é de 2× a 40× mais rápida que a varredura linear simples para raios de até
  2 km. Com N = 10.000 e raio de 2 km, fica em torno de 3 ms.
- A varredura linear com pré-filtro de caixa, porém, é mais rápida que a Trie para raios a partir
  de 1 km. Com p = 5 o bloco 3×3 cobre metade da frota, e percorrer a Trie em Python custa mais por
  entregador do que duas comparações de ponto flutuante.
- A Trie só ganha das duas varreduras quando a célula é pequena (raio de 0,5 km, precisão 6),
  porque aí examina 2% a 7% da frota.

O gargalo é a granularidade fixa do Geohash: a precisão salta de 6 para 5 quando o raio passa de
~0,61 km, e a área pesquisada cresce cerca de 30 vezes.
