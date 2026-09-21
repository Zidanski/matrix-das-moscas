# F3 — Mundo da superfície, replay e visualizador (2026-09-21)

## 1. O que foi construído

**`world/`** (Python, cm de escala mosca, segundos biológicos)
- `world.yaml`: arena circular de 40 cm de raio com colinas gaussianas de cor
  chapada, ciclo dia/noite de 60 s (luz = 0,5 + 0,5·cos), objetos (4 esferas
  que rolam com superfície doce/amarga/neutra, 2 cubos fixos sendo um oco, 2
  prismas com odor de CO2 e comida, 3 manchas no chão sendo duas de açúcar a
  3 cm uma da outra para o S1, 1 lago), parâmetros dos sentidos e as 6 moscas
  (Ada, Bia, Cleo fêmeas; Dan, Edu, Fil machos; cor e semente próprias).
- `geometry.py`: terreno, objetos, rumo relativo e divisão esquerda/direita.
- `physics.py`: `apply_motor` converte o `MotorState` lido dos neurônios em
  deslocamento e o mundo reage: parede, cubos bloqueiam, esferas rolam quando
  empurradas, lago prende quem entra mais de 1 cm até outra mosca encostar,
  salto da fibra gigante para o lado oposto ao looming, fome sobe sem comer.
- `senses.py`: situação física → `SensoryState` por lado: gustação por contato
  (açúcar, amargo, água, pernas), odores por gaussianas amostradas nas duas
  antenas (comida, CO2, geosmina), cVA em volta de cada macho, contato
  cuticular (ppk23, só o macho tem a população), canção audível a 4 cm,
  toque na antena (JO-CE) ao encostar em parede/objeto/mosca, looming por
  taxa de expansão angular de moscas e esferas em movimento, objeto pequeno
  em movimento (LC11). Noite: odores 0,6×, vultos 1,3×.
- `simulation.py`: um "dia" = 6 processos (um por mosca, cérebro com mmap
  compartilhado, no máximo 4 ativos por vez), loop de 15 ms, eventos
  (encontros, saltos, presa/resgate na água, esfera empurrada, mudanças de
  estado), métricas por mosca e por dia. `matrix simulate --days N --seconds S
  --brain reduced|full [--control Fil]`.

**`replay/format.py`**: `manifest.json` + `frames.bin` (float32 [ticks, 6,
campos]: pose, estado, fome, convulsão, disparos por janela, comandos, taxas
E/D/total das 19 populações de saída, valores E/D das 16 entradas) +
`objects.bin` + `events.json`. Leitor Python para métricas e testes.

**`web/`** (Vite + TypeScript + Three.js, sem pós-processamento, sombra só
do sol): céu em gradiente, sol octaédrico, nuvens em caixa, terreno de
colinas chapadas, objetos low-poly, moscas procedurais com dimorfismo (macho
menor, abdome escuro; fêmea maior), asas animadas por estado, nome flutuante
com a cor da mosca. Painel da mosca selecionada (estado, velocidade, fome,
convulsão, Hz de MN9/GF/oDN1/DNa01/DNa02/MDN/P1/pIP10, rótulo do cérebro
reduzido/completo, luz). Linha do tempo com marcadores de eventos, play/pause,
velocidade 0,25–4×, câmeras livre / seguir mosca / de cima. `npm run dev` em
`web/` (serve `../runs`).

Testes: 31 passam (7 novos do mundo com cérebros-fantoche, usados só para
exercitar física, sentidos e replay).

## 2. Regra de ouro, verificada

Nenhuma linha de `world/` escolhe destino, alvo ou ação para uma mosca. A
única entrada de movimento é o `MotorState` do decodificador; o mundo só
transforma a situação em estímulos e reage fisicamente. Consequência
observada na primeira rodada: **cascata de sobressaltos**. Um disparo isolado
da fibra gigante (6 Hz na janela de 75 ms) fazia a mosca saltar; o salto a
8 cm/s vira looming para as vizinhas, que saltavam também, e todas pulavam
juntas a cada segundo. Correção registrada como intervenção: o salto exige a
taxa total dos dois GF acima de 20 Hz (~3 disparos em 30 ms; looming real dá
50–150 Hz). Ainda assim os sobressaltos em cadeia existem e são do modelo.

## 3. Custo

| Configuração | Parede por s biológico (6 moscas) |
|---|---|
| 3 fêmeas k=3 (25 793 neurônios) + 3 machos k=3 (33 550) | ~5 s (mais ~20 s de arranque dos processos) |
| dia de 60 s | ~6 min |

Cérebros completos ficam para dias curtos de destaque (`--brain full`,
machos a ~19× o tempo real cada).

## 4. Os primeiros dias (60 s cada, cérebros reduzidos k=3)

**Dia 0, antes da calibração motora** (ganho 0,02 cm/s por Hz): oDN1 disparava
a 6–16 Hz com odor de comida, mas as moscas andaram 0,05–4 cm em um minuto.
Ninguém comeu, ninguém se encontrou. Intervenção registrada: ganhos de marcha
0,15, giro 0,15, ré 0,08 (marcha resultante 0,3–0,6 cm/s média, picos 2 cm/s).

**Dia 0, depois** (`runs/day_0000`, 346 s de parede):

| Mosca | distância (cm) | tempo comendo (s) | tempo andando | ré | saltos | convulsão |
|---|---|---|---|---|---|---|
| Ada ♀ | 0,5 | 0 | 2 % | — | 0 | 0 |
| Bia ♀ | 8,5 | 0 | 35 % | — | 0 | 0 |
| Cleo ♀ | 6,0 | 0 | 22 % | — | 0 | 0 |
| Dan ♂ | 22,0 | 0 | 57 % | 10 % | 0 | 0 |
| Edu ♂ | 4,5 | **1,15** (achou a bola doce) | 21 % | 1 % | 0 | 0 |
| Fil ♂ | 7,2 | 0 | 32 % | 2 % | 1 | 0 |

Encontros macho-fêmea a menos de 1 cm: 0; esferas empurradas: 0. As moscas
partem de posições ao acaso num raio de 12 cm e andam devagar, então um
minuto é pouco para se cruzarem; a estatística de encontros vem dos dias
seguintes (abaixo) e dos 100 dias da F5. O que já se vê no replay: fêmeas
andam quando o odor de comida chega às antenas (oDN1/DNa), machos alternam
marcha e ré (MDN por toque na antena), Edu come quando pisa na bola doce
(MN9), e ninguém entrou em convulsão em 6 cérebros × 60 s.

## 5. Limitações desta fase

- "Seguir a fêmea" e "tentar cópula" não existem: o LIF não produz
  perseguição; o macho só canta (pIP10) quando os neurônios mandam, e o
  movimento continua vindo de oDN1/DNa. É lacuna, não código.
- Cerdas de perna não existem em nenhum conectoma acessível: contato usa
  gustação de perna e JO-CE (documentado na F2).
- Física 2D sobre o mapa de altura (sem pernas, sem inércia); esferas com
  atrito simples; lago como disco.
- O replay guarda taxas de populações, não disparos por neurônio (o painel
  do cérebro da F5 vai amostrar somas por processo).
