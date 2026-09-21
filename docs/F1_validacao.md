# F1 — Dados, motor, validação e benchmark (2026-09-21)

Arquivos brutos dos resultados em `docs/F1_validacao/`. Tudo abaixo foi medido
nesta máquina (i5-8350U, 16 GB, Windows 11, Python 3.11, numba 0.67).

## 1. Dados → pacotes CSR

| Pacote | Origem | Neurônios | Arestas | Anotados | Tamanho em disco |
|---|---|---|---|---|---|
| `flywire783` | Shiu `Connectivity_783.parquet` + anotações v3.1.0 | 138 639 | 15 091 983 | 137 147 | 96 MB |
| `flywire630` | Shiu `2023_03_23_connectivity_630_final.parquet` (só para conferência com o artigo) | 127 400 | 14 687 178 | 106 214 (IDs v783 que sobreviveram) | 90 MB |
| `malecns10` | MaleCNS v1.0 `traced-only` + anotações + NT (cérebro **e** VNC) | 165 122 | 24 975 257 | 162 517 | 150 MB |

Regras: pesos = contagem de sinapses com o sinal do pré-sináptico (int16);
MaleCNS: `status == Traced`, sinal pela regra de Shiu sobre `consensus_nt`
(ACh/DA/OA/5-HT +, GABA/Glu/histamina −, `unclear` = 0 → 3 602 neurônios sem
saída). Conversão em duas passadas por lotes do pyarrow; pico de RAM < 1,5 GB.

Lado no MaleCNS: `somaSide`, senão `rootSide` (sensoriais). As populações
sensoriais do macho são assimétricas nos dados (ORN_DA1: 105 D, 51 E, 48 sem
lado; ORN_V: 39 D, 16 E). Isso é o conectoma, não a conversão.

Populações por rótulo (nunca por ID) em `brain/types.py`; relatório completo
com `population_report()`. Destaques: FlyWire `LB3` açúcar 129 (67 E / 62 D),
amargo 65, MN9 = `CB0701` 1/1, pC1a–e 10, aIPg 23, vpoDN 2; MaleCNS `LB3b/c`
açúcar 34, `LgLG5–8` (ppk23) 64, P1 (`pC1_*`) 148, TkFruM 5, pIP10 2, vPR6 8.

## 2. Motor event-driven

`brain/engine.py`: kernel Numba, estado só dos neurônios ativos, anel de
atraso de 18 passos, integração exata (equivale ao método `linear` do Brian2),
Poisson por Bernoulli por passo, eventos externos determinísticos, ganho por
neurônio pós-sináptico (individualidade), contagens por neurônio. Nunca há
multiplicação esparsa por passo.

Dois detalhes do modelo publicado que **não estão no artigo** e foram
descobertos comparando com o Brian2 e com o `model.py`:

1. Variáveis `(unless refractory)` no Brian2 recebem "escrita condicional":
   entrada sináptica, Poisson ou externa que chega a um neurônio refratário é
   **descartada**, não acumulada (verificado experimentalmente e no código
   `neurongroup.py: set_conditional_write`).
2. No `model.py` de Shiu, os alvos do Poisson têm `rfc = 0` ("no refractory
   period for Poisson targets"): disparam a ~99 Hz quando estimulados a 100 Hz,
   com ISI mínimo de 0,2 ms. Confirmado nos arquivos de disparos publicados
   (`results/example/sugarR_100Hz.parquet`: GRNs a 99,0 Hz, ISI mínimo 0,2 ms).

Sem o item 2 nossas taxas ficavam 12 % abaixo do publicado; com ele, batem.

Limiar de desativação `eps = 1e-2 mV`: trens de disparo idênticos aos de
`1e-4 mV` nos dois conectomas (2 sementes cada); em `5e-2 mV` divergem
(`eps_sensitivity.json`).

Testes (`uv run pytest`, 18 passam): parâmetros, silêncio sem entrada, kick →
disparo no passo seguinte, espaçamento refratário (23 passos), descarte de
entrada no refratário, integração exata contra a forma fechada, inibição,
ganho, persistência entre chunks, desativação sem perda de disparos, alvos de
Poisson sem refratário (~99 Hz vs ~82 Hz), **equivalência disparo a disparo
com o Brian2** em rede de 12 neurônios com pesos mistos e 80 kicks, CSR em
fluxo, ida e volta em disco, transposição e subcircuito, embaralhamento com
preservação de grau, pacotes reais.

## 3. Validação: açúcar → MN9, amargo reduz

### 3a. Protocolo exato de Shiu et al. 2024 (v630, 21 GRNs de açúcar D, 30 trials de 1 s)

| | MN9 E (Hz) | MN9 D (Hz) | disparos/trial (mediana) | trials disparados |
|---|---|---|---|---|
| Publicado, 100 Hz (Brian2, repositório de Shiu) | 67,0 | 48,6 | 9 642 | — |
| **Nosso motor, v630, 100 Hz** | **67,0** | **48,4** | **9 704** | 0/30 |
| Publicado, 200 Hz | 93,3 | 61,8 | 17 070 | — |
| **Nosso motor, v630, 200 Hz** | **90,7** | **62,7** | **16 898** | 0/30 |
| Nosso motor, v630, açúcar 100 + amargo 100 Hz | 4,2 | 10,3 | | 0/30 |
| Nosso motor, v783 (20/21 IDs; MN9 D mudou de ID), 100 Hz | 62,1 | — | 8 996 | 0/30 |
| Nosso motor, v783, 200 Hz | 90,0 | — | 16 176 | 0/30 |
| Nosso motor, v783, açúcar 100 + amargo 100 Hz | 3,0 | — | | 0/30 |

Portão cumprido no FlyWire: açúcar sobe MN9, amargo o reduz a < 10 %, e os
números batem com a simulação publicada dentro de 3 %.

### 3b. Protocolo do mundo (populações por rótulo, lado D inteiro)

Estimular **toda** a população `LB3` direita (62 neurônios no v783, 50 no
v630; o artigo usa 21) é ~3× mais forte que o artigo e revela uma
**bistabilidade do modelo**: em parte dos trials a 100 Hz, e em todos a
≥ 150 Hz, um laço recorrente do lobo antenal e do corpo cogumelar (APL, DPM,
lLN1_bc, v2LN30, células de Kenyon) se auto-sustenta a ~48 000 disparos por
100 ms em ~8 500 neurônios, e MN9 cai. O Brian2 faz o mesmo (mesmos neurônios,
mesma escala). Isso é propriedade do LIF sem adaptação com estas constantes,
não do motor; fly-brain-minecraft contorna com ganho 0,25 nas células de
Kenyon. Para o mundo isso vira uma regra de configuração: taxas sensoriais
calibradas para ficar abaixo do limiar de ignição, e o estado "convulsão"
detectado e registrado no diário quando ocorrer.

Resultados por rótulo (v783 e MaleCNS): seção 6 e os CSV `*_sugar_sweep.csv`
/ `*_bitter_vs_sugar100.csv`.

## 4. Benchmark (1 s biológico, açúcar D a 100 Hz, uma mosca, um núcleo)

| Pacote | Neurônios | Arestas | Parede por s bio | Disparos/s | RSS |
|---|---|---|---|---|---|
| `flywire783` (completo) | 138 639 | 15,1 M | **0,5 s** | 9 087 | ~200 MB |
| `flywire783_k4` | 90 757 (65 %) | 11,4 M | 1,1 s (com contenção de CPU) | 9 087 | 199 MB |
| `flywire783_k3` | 24 310 (18 %) | 2,7 M | 0,3 s | 7 530 | 171 MB |
| `malecns10` (completo, com VNC) | 165 122 | 25,0 M | 19 s (trial estável) / 61 s (trial disparado) | 40 807 / 692 045 | ~240 MB |
| `malecns10_k4` | 124 599 (76 %) | 20,6 M | 15,8 s | 26 293 | 227 MB |
| `malecns10_k3` | 32 143 (19 %) | 5,3 M | 3,1 s | 32 371 | 186 MB |

Leitura: o cérebro completo da fêmea roda **2× mais rápido que o tempo real**
por mosca; o CNS do macho com as constantes de Shiu é muito mais ativo
(2 316 neurônios disparando e 32 000 ativos com 17 GRNs estimulados) e roda a
~19× o tempo real. O custo escala com a atividade, não com o tamanho: o
subcircuito k=4 quase não ajuda porque preserva 75–83 % das arestas; k=3
corta 5×. Um "dia" de 60 s com 6 moscas (3 fêmeas completas + 3 machos k3)
custa ~10 min de parede; com machos completos, ~1 h. Rotular sempre no HUD.
Memória: < 250 MB por processo; CSR compartilhado por mmap.

## 5. Modo controle

`brain/shuffle.py`: embaralhamento de alvos pós-sinápticos que preserva grau de
saída, grau de entrada e a distribuição de pesos/sinais por linha. Testado.

## 6. Resultados por rótulo (v783, MaleCNS) e frequência de ignição

Protocolo: toda a população de açúcar do lado D (v783: 62 `LB3`; MaleCNS: 17
`LB3b/c`), 5 trials de 1 s por taxa; "estável" = média só dos trials sem
ignição; "ign." = fração de trials com ignição (> 10 000 disparos nos últimos
100 ms).

| Taxa (Hz) | v783 MN9 E / D estável (Hz) | v783 ign. | MaleCNS MN9 E / D estável (Hz) | MaleCNS ign. |
|---|---|---|---|---|
| 10 | 0 / 0 | 0/5 | 0,8 / 0 | 1/5 |
| 25 | 0 / 0 | 0/5 | 9,0 / 0 | 4/5 |
| 50 | 9,0 / 10,0 | 0/5 | 17,2 / 0 | 1/5 |
| 100 | — (todos ignizados; MN9 7 / 5) | 5/5 | 42,0 / 0 | 3/5 |
| 150 | — | 5/5 | 73,2 / 0,5 | 1/5 |
| 200 | — | 5/5 | 96,4 / 1,8 | 0/5 |
| açúcar 100 + amargo 50 | — | 5/5 | 6,0 / 0 | 3/5 |
| açúcar 100 + amargo 100 | — | 5/5 | 0,3 / 0 | 2/5 |
| açúcar 100 + amargo 200 | — | 5/5 | — | 5/5 |

Ignição no v783 com 62 GRNs a 100 Hz: nosso motor 5/5, Brian2 (mesma
referência corrigida) 6/6 — o comportamento é o mesmo nos dois simuladores
(`flywire783_brian2_explosion_seeds_v2.json`). Antes da correção do
refratário dos alvos (drive ~18 % menor) a ignição era parcial: nosso motor
2/10, Brian2 5/9.

Leitura:
- **FlyWire (fêmeas)**: o portão passa no protocolo do artigo (seção 3a). Com
  a população inteira, o modelo ignita a partir de ~100 Hz; a 50 Hz é estável
  com MN9 ≈ 10 Hz. Consequência para o mundo: a taxa de GRNs de açúcar por
  neurônio deve ficar ≤ 50–60 Hz quando a população inteira é estimulada (ou
  estimular um subconjunto do tamanho do artigo). Vai para a configuração da F2.
- **MaleCNS (machos)**: **portão cumprido** — MN9 E sobe monotonicamente com o
  açúcar (0,8 → 96 Hz) e amargo 100 Hz reduz MN9 de 42 Hz para 0,3 Hz. Duas
  observações: (1) MN9 D não responde ao açúcar do lado D (no FlyWire o lado
  contralateral responde mais, mas o ipsilateral também responde); pode ser a
  convenção de lado dos sensoriais (`rootSide`) ou a fiação do macho — a ser
  checado na F2 estimulando o lado E; (2) a ignição no macho ocorre em qualquer
  taxa, inclusive 10 Hz (1/5) e 25 Hz (4/5), e some a 200 Hz (0/5): é um laço
  que se acende por acaso, não por excesso de drive. Isso, mais a atividade de
  fundo alta (2 300 neurônios disparando com 17 GRNs), é o efeito de reutilizar
  as constantes do FlyWire num CNS com VNC. Na F2 o ganho global do macho
  (config, premissa declarada) será medido para reduzir a ignição espontânea.

## 7. Estado do portão da F1

| Critério | Resultado |
|---|---|
| Dados dos dois conectomas → CSR (< 6 GB no preparo, < 1,5 GB por processo) | OK (pico < 1,5 GB; 96–150 MB por pacote) |
| Motor event-driven, sem SpMV por passo | OK (Numba, conjunto ativo) |
| Comparação com Brian2 no FlyWire | OK: disparo a disparo em rede pequena; taxas e contagens no cérebro completo (300 ms: 2 594 vs 2 707 disparos); reprodução do resultado publicado de Shiu dentro de 3 % |
| Açúcar → MN9 sobe, amargo reduz, nos dois conectomas | OK nos dois (FlyWire pelo protocolo do artigo; MaleCNS pelo protocolo por rótulo) |
| Benchmark, subcircuito reduzido, controle embaralhado | OK (seções 4 e 5) |
| Testes | 18 passam |

Pendente para commit: identidade git e login do `gh` (ação do usuário).
