# F5 — Painel do cérebro, câmeras, vídeo, métricas e os 100 dias (2026-09-21)

## 1. O que foi construído

- **Amostra neural no replay**: cada mosca grava, por janela de 15 ms, quais
  dos 20 000 neurônios amostrados (só os com soma anotado no próprio
  conectoma) dispararam (`spikes.bin`, `spikes_ptr.bin`, `soma_<i>.bin`).
  ~7 MB por dia de 60 s. Classes por cor: central, óptico, descendente,
  motor, ascendente, VNC, células de Kenyon.
- **Painel do cérebro** (🧠): nuvem de somas da mosca selecionada com as
  coordenadas do seu conectoma (FlyWire para as fêmeas, MaleCNS com VNC para
  os machos), acendendo com os disparos gravados e decaindo em ~120 ms; traços
  de ORN DM1, LC4, MN9, GF, oDN1 e DNa02 nos últimos 6 s.
- **Corte "Matrix"** (🟩): o mundo fica translúcido e o cérebro aparece por
  trás, em tela cheia.
- **Vídeo** (⏺): grava o canvas em WebM (VP9) pelo MediaRecorder do navegador
  e baixa o arquivo ao parar.
- **Câmeras**: livre, seguir mosca, de cima, câmera de segurança do
  laboratório (F4) e o corte Matrix.
- **Relatório**: `uv run matrix report --runs runs/cem --out docs/F5_relatorio`
  lê os manifestos, escreve `dias.csv`, `relatorio.md` (médias ± desvio, normal
  vs controle, por mosca, segredos) e `dias.png`.
- **100 dias**: `scripts/run_100_days.ps1` roda os dias 100–149 (normal) e
  150–199 (Fil com conectoma embaralhado preservando grau) em `runs/cem/`,
  com log em `runs/cem/log.txt` (termina com `FIM`).

## 2. Métricas por dia (definições)

| Métrica | Como é medida |
|---|---|
| distância percorrida | soma dos deslocamentos por tick, por mosca |
| tempo comendo | ticks em estado *comendo* sobre açúcar |
| encontros macho-fêmea | pares M-F a menos de 1 cm; tempo somado |
| cortes iniciadas | transições para o estado *cantando* (pIP10 acima do limiar) |
| fugas | saltos da fibra gigante |
| capturas | eventos `captura` dos robôs |
| índice de agregação | fração do tempo a menos de 1 cm de outra mosca |
| progresso nos segredos | "quase" e "disparou" por segredo e por dia |
| convulsão | janelas com mais de 10 000 disparos por 100 ms |

## 3. Resultado dos 133 dias simulados (`docs/F5_relatorio/`)

O que rodou: 100 dias de 30 s biológicos (200–249 normais, 250–299 com Fil de
conectoma embaralhado) e 33 dias de 60 s (100–104 normais; 150–177 controle:
o primeiro lote de controle, que deveria ter sido interrompido, continuou
rodando em paralelo durante a tarde; os dias completos ficaram). Total de
21,8 h de parede, 4 000 s biológicos por sexo-condição no mínimo. Todas as
contagens abaixo são por 60 s biológicos.

| Métrica (por 60 s) | Normal (n=55 dias) | Controle, Fil embaralhado (n=78) |
|---|---|---|
| encontros a < 1 cm | 1,53 ± 1,45 | 1,74 ± 2,05 |
| tempo macho-fêmea a < 1 cm (s) | 1,27 ± 3,47 | 1,72 ± 5,85 |
| pares macho-fêmea que se encontraram | 0,87 ± 0,98 | 0,68 ± 0,93 |
| cortes iniciadas (canção, pIP10) | 85,6 ± 97,9 | 60,9 ± 80,4 |
| fugas (saltos do GF) | 169 ± 62 | 146 ± 68 |
| capturas por robôs | 0,02 ± 0,13 | **0,35 ± 0,89** |
| entradas no laboratório | 0,56 ± 0,98 | 0,50 ± 0,80 |
| esferas empurradas | 0,47 ± 0,92 | 0,67 ± 1,04 |
| presas no lago | 0,89 ± 1,38 | 0,60 ± 1,19 |
| janelas em convulsão | **0** | 0,35 ± 2,39 (todas de Fil) |
| índice de agregação (fração do tempo a < 1 cm) | 2 % | 1 % |
| moscas que fugiram | 0 | 0 |

Por mosca (média por 60 s): fêmeas andam 13–16 cm e comem 8–11 s; machos
andam 26–30 cm e quase não comem (0,2–0,7 s). Só o macho embaralhado (Fil no
controle) foi capturado com frequência: **18 capturas contra 1 de todas as
outras moscas em todos os dias**, e só ele teve convulsões (27 janelas). O
embaralhamento preserva os graus, mas destrói o caminho looming → fibra
gigante: sem salto, o contato com o robô vira captura. Esse é o efeito de
controle mais nítido do experimento; encontros, cantos e distâncias não
diferem de forma clara entre as condições (as diferenças estão dentro de um
desvio padrão).

**Segredos**

| Segredo | quase | disparou | onde |
|---|---|---|---|
| S1 placa dupla | 232 | **16** (12 % dos dias) | duas fêmeas comendo nas manchas a 3 cm |
| S2 corredor de corte | 1 | 0 | nenhum casal no laboratório ao mesmo tempo |
| S3 alavanca | 17 | **3** (dias 265, 266, 281) | sempre Dan: afunda pelo lago, cai na rota de R2, é perseguido e salta na alavanca |
| S4 elevador | 6 | 0 | nunca 3 moscas dentro com a porta aberta |

**Escapadas: zero em 133 dias.** O cálculo feito antes de rodar (com 11 dias)
previa S3 em ~12 % dos dias e S4 em ~10⁻⁷; o observado foi S3 em 2,3 % dos
dias e S4 nunca, coerente com a previsão dentro da margem de um evento raro.
O gargalo é o previsto: não existe reflexo de agregação nas moscas, e o
elevador de 25 cm² precisa de três ao mesmo tempo.

**Intervenção recomendada, não aplicada.** O brief prevê ajustar distâncias
e ganhos e registrar como intervenção se nada disparar. S1 e S3 disparam;
S4 não. Para dar chance ao S4 sem inventar comportamento, as opções são
`min_flies: 2` no elevador ou uma zona maior perto da entrada do lago (onde
Dan cai). Fica registrada aqui como proposta para o dono do experimento
decidir; a configuração continua a original.
