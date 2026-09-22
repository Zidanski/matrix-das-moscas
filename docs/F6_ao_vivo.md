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

Cada tick do replay tem o campo `gamified` (0 = reflexo, 1 = camada Sims) e
as três necessidades; o HUD e o dossiê mostram qual camada está no comando.
Os estados novos `dancando` e `flertando` têm animação própria.

## 2. Fugas mais frequentes (intervenções registradas em `config.yaml`)

| Segredo | Antes | Agora |
|---|---|---|
| S2 porta | macho cantando a < 2,5 cm com fêmea a < 5 cm do outro lado; 10 s aberta | canção a < 4 cm com fêmea a < 12 cm no laboratório; 20 s aberta |
| S3 alavanca | salto a < 0,8 cm; gerador 20 s | salto a < 1,5 cm; gerador 25 s |
| S4 elevador | 5×5 cm em (17,−11), 3 moscas, 20 s após S3 | 8×8 cm em (14,4), ao lado da entrada do lago, **2 moscas**, 40 s após S3 |

## 3. Modo ao vivo (`uv run matrix live`)

`scripts/live.py` roda um dia normal (gravado em `runs/live/`) e transmite
cada tick por WebSocket (`ws://localhost:8765`): pose, estado, taxas,
entradas, robôs, mecanismos e os disparos amostrados dos 20 000 somas. No
visualizador, a opção **🔴 AO VIVO** do seletor conecta; o botão de play vira
"acompanhar ao vivo" e a barra de tempo permite voltar no que já passou. O
tempo real desta máquina é ~0,2× (5 s de parede por segundo biológico com 6
cérebros reduzidos): a transmissão é em câmera lenta, e o HUD mostra isso.

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

Barras de fome, social, diversão e romance; traços derivados do histórico
("gosta de água", "assustadiça", "galanteador", "vive levando fora", "curiosa:
vive no laboratório"); relações ("Fil tem interesse romântico em Ada ♥♥",
"melhor amigo de Dan"); e os últimos 14 acontecimentos em texto ("14,3 s — Dan
empurrou bola_amarga_1", "foi perseguido por R2", "ACIONOU S3!"). Tudo é
derivado dos eventos e campos gravados, no replay ou ao vivo.

## 6. Verificação

Testes: 40 passam (`tests/test_social.py` cobre a camada social, o modo Deus
e um dia com fantoches ociosos). Servidor ao vivo testado com cliente Python
(hello, 400 ticks, comandos aplicados) e no navegador: transmissão, dossiê,
painel Deus (comida, convulsão, romance no máximo), objetos criados ao vivo.
