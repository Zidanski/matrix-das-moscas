# F4 — Robôs, laboratório, segredos S1–S4, linha do tempo e diário (2026-09-21)

## 1. O que foi construído

**Mundo (ajustes pedidos):** arena de 25 cm (era 40), moscas nascem num raio
de 6 cm, mais árvores (10) e formas (pirâmides, toros, colunas) só visuais.
Visualizador: moscas no chão, pulinhos ao andar, arco no salto, balões de
pensamento e camada "The Sims" (humor, pensamentos, gostos). **Tudo nessa
camada é leitura do replay**: um pensamento só aparece se o sensor
correspondente estava ativo; o humor vem do estado, da fome, de saltos
recentes, de convulsão ou captura; os gostos são o que a mosca mais fez até
aquele instante. Nada disso existe no cérebro nem influencia o comportamento.

**Laboratório (`world/lab.py`, `world.yaml` → `lab`):** retângulo de 40×28 cm
sob a superfície com parede central e a porta S2 no meio, sala dos robôs a
leste (alavanca do gerador, elevador), corredor de chegada a oeste (com uma
mancha de açúcar: o laboratório alimenta os sujeitos), sala das telas ao
norte. Três entradas físicas: a **rampa** (o prisma de CO2 da superfície),
a **escotilha** sob o cubo oco (só abre com S1) e o **fundo do lago** (presa
na água por mais de 8 s sem resgate: afunda). Saídas: o elevador (S4) ou ser
carregada por um robô.

**Robôs (`world/robots.py`):** máquinas de estado, sem IA: patrulha por
rota → persegue mosca a menos de 7 cm no mesmo nível → captura se o contato
dura 1,5 s sem a mosca saltar → carrega até o elevador e a solta na
superfície → patrulha. Gerador desligado (S3) congela os robôs. R3 só sai
para a "manutenção" da superfície à noite (luz < 0,3). Para as moscas, um
robô é apenas um vulto (LC4/LPLC2 por expansão angular), um objeto que se
mexe (LC11) e um contato na antena (JO-CE).

**Segredos (`world/secrets.py`):** cada um é um mecanismo físico com
contagem de "quase" e "disparou", com instante e moscas:

| Segredo | Dispara quando | "Quase" |
|---|---|---|
| S1 placa dupla | duas moscas em estado *comendo* ao mesmo tempo nas duas manchas de açúcar a 3 cm → escotilha aberta 20 s | uma comendo e outra a < 3 cm da segunda mancha |
| S2 corredor de corte | macho com `song` ativo a < 2,5 cm da porta **e** fêmea a < 5 cm do outro lado → porta aberta 10 s | macho cantando sem fêmea, ou par sem canção |
| S3 alavanca | mosca em *salto* a < 0,8 cm da alavanca enquanto um robô a persegue → gerador desligado 20 s (robôs congelam) e elevador aberto 20 s | salto na alavanca sem robô; perseguida perto sem saltar |
| S4 elevador | 3+ moscas dentro do elevador aberto → sobe: **fuga** (as moscas saem do mundo) | 1–2 dentro com ele aberto, ou 3 com ele fechado |

**Diário (`world/diary.py`):** texto em português gerado por regras a partir
dos eventos, das métricas e do registro dos segredos; salvo em `diario.md`
em cada dia e embutido no manifesto (botão 📓 no visualizador).

**Replay:** novo `world.bin` com posição, nível e estado de cada robô e o
estado dos quatro mecanismos por tick; campo `level` por mosca. Linha do
tempo com marcadores de entrada no laboratório, perseguição, captura,
soltura, segredo quase/disparado e fuga. Câmera de segurança do laboratório.

Testes: 37 passam (6 novos: rampa e paredes, escotilha e lago, robôs,
segredos, diário, dia com laboratório).

## 2. Regra de ouro, mantida

O laboratório só reage: a rampa leva quem pisa nela, a escotilha só existe
quando S1 abriu, o lago afunda quem ficou preso, os robôs perseguem quem
está perto e carregam quem não saltou. Nenhum segredo é impossível para uma
mosca sozinha (S1 precisa de duas, S2 de um casal, S3 de um robô, S4 de três),
mas todos são improváveis, e os únicos reflexos sociais confirmados na F2 são
fracos (pIP10 a 6 Hz no macho). O experimento é medir isso.

## 3. Os primeiros dias com laboratório (60 s, cérebros reduzidos k=3, arena de 25 cm)

**Dia 20** (`runs/day_0020`, 293 s de parede, `loom_gain` ainda 0,25): as
moscas andaram muito mais no mundo menor (Cleo 69 cm, Fil 68, Edu 59, Dan 58),
Dan cantou 14× e Edu 3×, R3 saiu à noite (19 s) e perseguiu Cleo, Dan ficou
preso no lago e escapou saltando várias vezes. Mas houve **447 saltos**: no
mundo apertado o salto de uma mosca (8 cm/s a 1–2 cm) é um vulto máximo para
as vizinhas, que saltam também. Intervenção registrada: `loom_gain` 0,25 →
1,0 rad/s (só aproximações rápidas e próximas saturam LC4: robôs, esferas,
saltos a menos de 1,6 cm).

**Dia 21** (`runs/day_0021`, 411 s de parede, config atual):

| Mosca | distância | comeu | cantou | saltos | outros |
|---|---|---|---|---|---|
| Ada ♀ | 2 cm | **25 s** | — | 2 | 3 s a < 1 cm de Bia |
| Bia ♀ | 10 cm | — | — | 0 | **encontro com Ada aos 26 s** |
| Cleo ♀ | 5 cm | — | — | 0 | |
| Dan ♂ | 25 cm | — | 23× | 18 | empurrou a bola amarga aos 9 s |
| Edu ♂ | 16 cm | — | 12× | 22 | |
| Fil ♂ | 60 cm | — | **33×** | 47 | perseguido por R3 à noite (20 s) |

Primeiro **encontro** registrado (Ada e Bia, fêmea-fêmea), saltos caíram de
447 para 89, e os três machos cantaram (pIP10) sem nenhuma fêmea ao alcance
da canção: o reflexo existe, a coincidência não. Ninguém entrou no
laboratório (a rampa fica a 15 cm do centro; em um minuto as moscas cobrem
2–60 cm) e nenhum segredo chegou perto. O diário de cada dia está em
`runs/day_00XX/diario.md` e no botão 📓 do visualizador.

## 4. O que a F5 vai medir

100 dias com as métricas por dia (distância, tempo comendo, encontros
macho-fêmea, cortes iniciadas, fugas, capturas, índice de agregação,
progresso em cada segredo), comparação com o modo controle (`--control Fil`)
e, se em 100 dias nenhum segredo disparar, ajuste de distâncias e ganhos
registrado como intervenção. Também: painel do cérebro (nuvem de somas),
corte "Matrix", gravação de vídeo e README final.
