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

O tempo real desta máquina é ~0,2× (5 s de parede por segundo biológico com
6 cérebros reduzidos): a transmissão é em câmera lenta. Cada tick chega com
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

## 7. Verificação

Testes: 39 passam (`tests/test_social.py` cobre a camada social, o modo Deus
e um dia com fantoches ociosos). Servidor ao vivo testado com cliente Python
(hello, 400 ticks, comandos aplicados) e no navegador: transmissão, dossiê,
painel Deus (comida, convulsão, romance no máximo), objetos criados ao vivo.
