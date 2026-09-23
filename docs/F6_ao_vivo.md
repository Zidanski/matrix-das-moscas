# F6 — Modo ao vivo, camada social gamificada, modo Deus e dossiês (2026-09-22)

Pedido do dono do projeto depois dos 133 dias: um mundo mais vivo, com
interações frequentes (jogar bola, comer juntas, dançar, flertar), lista de
ações e relações ao clicar na mosca (estilo Dwarf Fortress), fugas mais
frequentes, simulação vista em tempo real e um "modo Deus". Com a licença
explícita de **gamificar** o que não vem do cérebro.

## 1. O que continua sendo cérebro e o que virou jogo

| Vem dos neurônios (LIF sobre o conectoma) | Camada gamificada (`world/social.py`, marcada no replay) |
|---|---|
| comer (MN9), fuga (fibra gigante), marcha e giro por odor (oDN1, DNa), ré (MDN), canção (pIP10), convulsão | necessidades **social**, **diversão**, **romance** que sobem com o tempo |
| toda leitura sensorial (odor, contato, looming, cVA, canção) | quando o cérebro fica ocioso por 0,3 s e uma necessidade passa de 0,6, a camada leva a mosca até o alvo (outra mosca, uma bola, um par) a 1 cm/s |
| | interações por proximidade: **comeram juntas**, **dançaram** (3 s), **jogaram bola** (chutou e outra recebeu em 6 s), **flerte** aceito ou rejeitado (2,5 s; aceite depende do romance da fêmea e da amizade do par) |
| | relações por par (amizade, romance) que crescem com as interações e decaem devagar |
| | **brinquedos** (`objects.playgrounds` no `world.yaml`): mesa de cartas (−8,−3) e roleta de cassino (7,8). Cada mosca tem um passatempo favorito (bola, cartas ou roleta, sorteado pela semente). Com 2+ moscas na mesa: **jogaram cartas** (4 s, vencedor sorteado leva 1 ficha de cada). Na roleta com diversão > 0,3 e fichas: **apostou** 1–3 fichas, giro de 3 s, 35 % de chance de dobrar. Todas começam com 10 fichas |

Cada tick do replay tem o campo `gamified` (0 = reflexo, 1 = camada Sims) e
as três necessidades; o HUD e o dossiê mostram qual camada está no comando.
Os estados novos `dancando`, `flertando`, `jogando_bola` (investida do chute),
`jogando_cartas` (cartas na mão) e `apostando` (pulinhos de torcida; a roleta
gira de verdade enquanto alguém aposta) têm animação própria.

**Por que a mosca se assustou.** Cada evento `salto` grava um `motivo`, lido do
que o sensor estava vendo naquele tick (`world/senses.py` guarda a fonte de
looming mais forte): "vulto de R2 (robô)", "vulto de bola_amarga_1 (bola
rolando)", "vulto de Dan (mosca se aproximando)", "barulho da canção perto da
antena" ou "sobressalto espontâneo (disparo isolado da fibra gigante)". O
dossiê mostra o motivo em cada susto e o motivo mais frequente vira traço
("o que mais assusta Ada: vulto de R3"). O diário lista os motivos do dia.

## 2. Fugas mais frequentes (intervenções registradas em `config.yaml`)

| Segredo | Antes | Agora |
|---|---|---|
| S2 porta | macho cantando a < 2,5 cm com fêmea a < 5 cm do outro lado; 10 s aberta | canção a < 4 cm com fêmea a < 12 cm no laboratório; 20 s aberta |
| S3 alavanca | salto a < 0,8 cm; gerador 20 s | salto a < 1,5 cm; gerador 25 s |
| S4 elevador | 5×5 cm em (17,−11), 3 moscas, 20 s após S3 | 8×8 cm em (14,4), ao lado da entrada do lago, **2 moscas**, 40 s após S3 |

## 3. Modo ao vivo de verdade (controlado pela tela)

`npm run dev` em `web/` sobe, além do visualizador, o servidor ao vivo
(`uv run matrix live`, WebSocket em `localhost:8765`), que fica esperando. No
visualizador, a opção **🔴 AO VIVO** conecta e mostra "pronto":

| Botão | Efeito |
|---|---|
| ▶ | cria os 6 cérebros (20–40 s) e começa um dia **sem fim**, em t = 0 |
| ❚❚ / ▶ | pausa e retoma o **tempo da simulação** (as moscas congelam) |
| ⏹ parar | encerra o dia, grava o replay em `runs/live/day_XXXX` e mostra o diário |
| ↺ reiniciar | para, grava, e recomeça do zero com cérebros novos |
| ⏭ agora | volta a acompanhar o presente depois de arrastar a barra para o passado |

O ritmo desta máquina é ~0,3× do tempo real (seção 8; era 0,12× antes das
otimizações): a transmissão é em câmera lenta, mas lisa a 60 fps porque o
visualizador interpola entre os quadros. Cada tick chega com
pose, estado, taxas, entradas, robôs, mecanismos e os disparos amostrados.

## 4. Modo Deus (⚡, só ao vivo)

| Grupo | Comandos |
|---|---|
| Língua | mudo da canção, do feromônio (cVA) e do contato: as moscas deixam de se ouvir, cheirar ou sentir |
| Cérebro da selecionada | reiniciar (estado LIF zerado), salvar estado, restaurar estado, convulsão (300 células de Kenyon a 200 Hz por 0,6 s) |
| Corpo | alimentar, teleportar para o centro, romance ou diversão no máximo |
| Mundo | + comida perto da selecionada, + bola, + robô na superfície, pausar, continuar |

Cada comando vira um evento `modo_deus` no replay e aparece no dossiê da
mosca como "sofreu intervenção divina".

## 5. Dossiê (clique na mosca)

Barras de fome, social, diversão, romance e fichas; traços derivados do histórico
("gosta de água", "assustadiça", "galanteador", "vive levando fora", "curiosa:
vive no laboratório", "viciada em roleta", "sortuda", "boa de cartas", "recua
muito"). Regra de coerência: **"gosta de" só aparece para o que é prazeroso ou
escolhido** (comer, passear, cantar, dançar, bola, cartas, roleta). Susto e ré
são reflexos de defesa, então nunca entram nos gostos: viram traços
("assustadiça"/"nervosa"/"destemida", "recua muito"). Os adjetivos concordam
com o sexo da mosca; relações ("Fil tem interesse romântico em Ada ♥♥",
"melhor amigo de Dan"); e os últimos 14 acontecimentos em texto ("14,3 s — Dan
empurrou bola_amarga_1", "foi perseguido por R2", "ACIONOU S3!"). Tudo é
derivado dos eventos e campos gravados, no replay ou ao vivo.

## 6. Primeiro dia ao vivo (240 s, com 3 comandos divinos) e o ajuste seguinte

`runs/live/day_0000`: 9 encontros (4 macho-fêmea), 2 flertes rejeitados (Dan e
Edu levaram fora de Ada), 2 danças (Ada com Edu, Dan com Fil), 1 partida de
bola, 1 refeição a dois; amizades nascendo (Ada-Edu 0,20, Dan-Fil 0,20,
Bia-Cleo 0,13). Machos andaram ~300 cm, Bia e Cleo comeram 175 s cada. Dois
freios ficaram claros: **1 251 saltos em cascata** (mosca saltando nunca fica
ociosa, então a camada não assume) e **ninguém entrou no laboratório** em 4
minutos (S2 a S4 dependem disso). Ajuste registrado como intervenção:
necessidades 2–3× mais rápidas, limiar 0,45, esperas menores, 1,5 cm/s,
desejo de **explorar** (rampa na superfície; porta e depois elevador no
laboratório) e `loom_gain` 2,0.

**Depois do ajuste** (`runs/teste_social/day_0500`, 60 s): 21 encontros, 7
flertes (2 aceitos), 3 danças, 3 partidas de bola, 3 refeições a dois, S1
disparou 2×, Ada e Fil entraram no laboratório (12 e 14 s), e já há casais em
formação (Bia-Dan romance 0,37; Ada-Fil 0,36) e amizades (Ada-Bia 0,38).
Saltos: 401 em 60 s, ainda muitos; a maior parte agora vem das próprias
aproximações a 1,5 cm/s. S2 a S4 ainda não dispararam neste dia; com moscas
entrando no laboratório, passam a ser possíveis, e a estatística virá de mais
dias (`matrix simulate` + `matrix report`).

## 8. Desempenho: 30 fps e o ritmo do ao vivo (2026-09-22)

Diagnóstico medido nesta máquina (i5-8350U, UHD 620):

| Onde | Custo | Conclusão |
|---|---|---|
| mundo (sensores, física, social, gravação), sem cérebro | 0,7 ms por tick | irrelevante |
| visualizador, 1024×768, sombras ligadas | 1,1 ms de `draw()` + 6,2 ms de render (55 draw calls, 77 k triângulos) | ~60 fps folgados; o dossiê aberto era o mais caro (recalculava traços a cada quadro) |
| cérebro fêmea k=3, estímulo típico, 1 núcleo | 1,05 s de parede por s biológico (58 % dos neurônios ativos) | |
| cérebro macho k=3, estímulo típico, 1 núcleo | 3,0 s por s biológico (88 % ativos, 28 k disparos/s) | **é o gargalo**: 10 000 passos/s × ~30 k neurônios ativos |

O "travado" do ao vivo não era o visualizador: era a simulação entregando ~8
ticks por segundo e o visualizador só redesenhando quando um tick chegava.
Três mudanças:

1. **Motor: lista de ativos ordenada** (`brain/engine.py`). A cada bloco de
   150 passos a lista de neurônios ativos é ordenada por índice, e o laço
   passa a ler `v/g/rfc_end` em sequência (cache). O resultado é bit a bit o
   mesmo (cada neurônio é independente dentro do passo; a entrega dos
   disparos segue o anel): contagens de disparo idênticas e o teste
   disparo a disparo contra o Brian2 continua passando. Medido: fêmea k=3
   1,05 → 0,78 s/s; macho k=3 3,0 → 1,43 s/s. `fastmath` sozinho não muda
   nada; intercalar `v` e `g` num só array piora.
2. **Escalonamento dinâmico** (`world/simulation.py`). Continua com no máximo
   4 cérebros ativos, mas assim que um processo devolve, o próximo entra
   (machos primeiro, por serem os mais lentos), em vez de dois grupos fixos
   que esperavam o mais lento de cada grupo.
3. **Visualizador liso a 60 fps** (`web/src/main.ts`). No ao vivo o relógio
   anda no ritmo medido de chegada dos ticks (janela de 2 s) e o desenho
   **interpola posição e rumo entre dois quadros gravados** (bolas e robôs
   também; teleporte > 3 cm não interpola). Estados, taxas e sensores
   continuam sendo os do quadro inteiro. O mesmo vale para o replay a 0,25×.
   Texturas dos balões de pensamento ficam em cache; o dossiê é
   recalculado a ~10 Hz. O relógio mostra os fps e, no ao vivo, o ritmo
   "×N do tempo real".

Ritmo do dia ao vivo com 6 cérebros reduzidos: **~0,3× do tempo real** (30 s biológicos em 123 s de parede, dos quais ~23 s são o arranque dos 6 processos; antes eram 60 s em 496 s, ~0,12×). O limite
que sobra é físico: 3 machos a ~1,4 s por s biológico cada, em 4 núcleos.
Para um ao vivo em tempo real de verdade seria preciso ou só as fêmeas (3 ×
0,8 s/s em paralelo ≈ tempo real) ou um subcircuito menor para os machos,
que precisaria passar de novo pelo SCREEN.

## 9. Fome mortal, o mundo mágico e os chapéus (2026-09-22)

Tudo desta seção é **camada gamificada** (não vem dos neurônios) e está
marcado como tal no replay e no dossiê.

- **Fome mortal só no subsolo.** `fly.starve_after_s` (45 s) em
  `world/world.yaml`: uma mosca que passa esse tempo **no laboratório sem
  comer** (só o tempo lá embaixo conta; lá não há comida) morre de fome: estado `morta`, fica de
  patas para cima, sem sensores, sem movimento, ignorada pelos robôs e pela
  camada social. Na superfície nunca morre (há comida por perto). **Exceção:
  a mosca capturada** — o robô a alimenta lá embaixo (o relógio de fome
  zera na soltura). Evento `morreu_de_fome`, linha no diário, traço no
  dossiê, `metrics._dia.mortes`. Modo Deus ganhou **reviver**.
- **A iluminada.** Quem o robô devolve à superfície volta `pregando`
  (evento `voltou_iluminada`): passa a contar do "mundo mágico que viu".
  Perto de uma mosca que ainda não acredita, faz um sermão de 3 s (ela
  `pregando`, a outra `ouvindo`). A chance de acreditar é
  `sermon_believe_base` (0,35) + 0,4·amizade + 0,3·romance. Quem acredita
  vira crente **e também passa a contar**; quem não acredita passa a "achar
  X maluca" (amizade cai 0,1; evento `achou_maluca`). Com
  `revolution_min_believers` (3) crentes, contando a profeta, dispara a
  **revolução** (evento `revolucao`): as crentes ficam com a curiosidade no
  máximo e marcham juntas para o laboratório (rampa → porta S2 → elevador).
  Se isso abre algum segredo continua dependendo dos mecanismos S1–S4; a
  revolução só junta as moscas no lugar certo. "Podendo ou não" é literal:
  as estatísticas contam.
- **Chapéus** (`hat:` por mosca no `world.yaml`, só visual): Ada cartola,
  Bia chapéu de palha, Cleo coroa, Dan boné, Edu chapéu de cowboy, Fil
  chapéu de mago. O chapéu balança no chute e no sermão.
- **Animações novas**: comer com **garfo e faca** (alternam, a cabeça acena),
  chute com recuo, investida e pulinho, cartas em leque que abre e fecha e
  uma carta jogada na mesa, sermão gesticulado, ouvinte de cabeça inclinada,
  morta de patas para cima.

Testes: `tests/test_social.py` cobre a morte no subsolo com a capturada
isenta e a superfície imune, a profeta que converte 3 e dispara a revolução,
e a cética que a acha maluca.

## 10. Ao vivo em tempo real de verdade e HUD novo (2026-09-23)

O dono reclamou, com razão: o relógio biológico do ao vivo andava a 0,1–0,3×
do relógio de parede, porque cada tick do mundo esperava os 6 cérebros e os
machos custam ~1,4 s por segundo biológico. Agora o servidor ao vivo roda o
**modo tempo real** (`Day(realtime=True)`; `uv run matrix live --sync`
devolve o modo síncrono exato):

- **O mundo anda no relógio de parede** (15 ms por tick, `time.sleep` até o
  instante certo; se atrasar mais de 1 s não tenta recuperar em rajada).
- **Os cérebros trabalham em paralelo e sem barreira**: até 4 em cálculo;
  assim que um devolve, recebe a janela seguinte (quem está ocioso há mais
  tempo entra primeiro). Enquanto um cérebro calcula, a mosca mantém o
  último comando motor (o salto, que é de um tick, não se repete).
- **Janelas puladas ficam registradas**: campo `brain_step` por tick (1 =
  o cérebro processou este tick). O HUD mostra "cérebro: N % dos ticks";
  o manifesto grava `realtime` e as métricas `fracao_de_ticks_com_cerebro`
  por mosca e `ritmo_parede` do dia. Consequência honesta: o tempo neural
  corre mais devagar que o mundo (com 20–25 % dos ticks, um reflexo que
  levaria 100 ms leva ~400 ms de mundo). O `simulate` offline continua
  síncrono e exato; só o ao vivo pula janelas.
- **Comandos de cérebro do modo Deus** com o cérebro ocupado entram numa
  fila e são aplicados quando ele devolve (não corrompe o pipe).
- **Arranque**: os 6 processos sobem em paralelo (antes, um por vez), os
  workers rodam com prioridade abaixo do normal (o navegador ganha a CPU) e o
  servidor **pré-aquece os cérebros do próximo dia** enquanto ninguém assiste
  (estado `warming`): o ▶ começa na hora, inclusive depois de parar/reiniciar.

Medido nesta máquina com o visualizador aberto: relógio a **0,97–0,99× do
tempo real**, 6 cérebros processando 20–26 % dos ticks cada, ▶ começando em
menos de 1 s. Teste `test_realtime_day_keeps_wall_clock_and_marks_skipped_windows`
usa cérebros falsos lentos e confere ritmo, `brain_step`, motor mantido e a
fila de comandos.

**HUD novo** (`hudHtml` em `web/src/main.ts`): nome grande com o chapéu,
humor em destaque, fichas de estado (estado, convulsão, laboratório, quem
está no comando: 🧠 reflexo ou 🎮 Sims), pensamentos como fichas, barras de
fome, velocidade, luz e cérebro, e as taxas de saída como ladrilhos com
palavras (comer, fuga, andar, girar, ré, corte, canção) que acendem quando
disparam. Barra inferior agrupada e que quebra linha em vez de estourar;
status do ao vivo numa pílula acima da barra; barras do dossiê em HTML.

## 11. Barra inferior, ritmo do ao vivo, painel do cérebro e convulsão visível (2026-09-23)

- **Barra inferior** em duas linhas (transporte e tempo em cima; câmera e
  painéis embaixo; ▾ recolhe a segunda linha, lembrado no navegador). Botões
  maiores, com estado ligado/desligado e desabilitados quando não fazem
  sentido (⏹ e ⏭ só com um dia em curso; ▶ trava enquanto começa/grava). No
  ao vivo o botão 🔴 fica vermelho cheio, aparecem ⏹ ↺ ⏭ e ⚡, o rótulo vira
  "velocidade do mundo" e uma dica explica cada botão.
- **Ritmo do ao vivo**: 0,25×, 0,5×, 0,75× e 1×. Comando `speed` do
  visualizador; `Day.rt_speed` divide o passo de parede. Mais lento = os
  cérebros processam uma fração maior dos ticks (a 0,25× quase todos).
- **Painel do cérebro** vira uma caixa própria (`#brainbox`) no lado
  esquerdo, abaixo do HUD, longe do dossiê: arrastável pelo cabeçalho
  (posição lembrada), com ◀ ▶ e seletor para trocar a mosca (troca a seleção
  inteira: HUD, dossiê e cérebro), botão – para esconder os traços e ✕ para
  fechar. O corte Matrix usa a mesma caixa em tela cheia.
- **Reconexão no meio do dia** (F5 com um dia em curso): o buffer do
  visualizador cresce até caber o primeiro tick recebido (antes estourava e
  a tela congelava em 0,0 s) e o desenho não volta antes desse tick.
- **Convulsão induzida garantida**: o comando ⚡ convulsão força o estado
  `convulsao` por 100 janelas do cérebro (1,5 s de tempo neural) enquanto
  injeta 200 Hz em 300 células de Kenyon; antes dependia de a tempestade
  passar do limiar de ignição, e às vezes não passava. A ignição natural
  continua dependendo do limiar.
- **Abrir replay × entrar no ao vivo**: o carregamento do replay é
  assíncrono; se o usuário entra no ao vivo enquanto ele carrega, o pedido
  antigo é abandonado (antes ele sobrescrevia o ao vivo e a tela congelava).
- **Convulsão visível**: com o estado `convulsao` a mosca treme violentamente,
  rola de lado, as pernas se debatem, o chapéu pula e as asas vibram; na
  nuvem de neurônios tudo pulsa em vermelho, os que disparam ficam brancos,
  a nuvem incha e a câmera treme (`BrainCloud.update(..., ignited)`).

## 7. Verificação

Testes: 39 passam (`tests/test_social.py` cobre a camada social, o modo Deus
e um dia com fantoches ociosos). Servidor ao vivo testado com cliente Python
(hello, 400 ticks, comandos aplicados) e no navegador: transmissão, dossiê,
painel Deus (comida, convulsão, romance no máximo), objetos criados ao vivo.
