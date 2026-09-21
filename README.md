# A Matrix das Moscas

Um mundo 3D assumidamente falso, habitado por 6 *Drosophilas* (3 machos, 3
fêmeas) cujo comportamento sai de emulações de cérebro inteiro baseadas em
conectomas reais: **FlyWire v783** para as fêmeas e **MaleCNS v1.0** para os
machos, ambos rodando o modelo LIF de Shiu et al. 2024 num motor event-driven
em CPU. Debaixo do mundo há um laboratório operado por robôs. Se as moscas
descobrirem os segredos, escapam. Talvez nunca escapem. Isso é o experimento.

Regra de ouro: **o código do mundo nunca move uma mosca.** O mundo transforma
a situação física em estímulos sensoriais e reage ao que as moscas fazem. Todo
movimento sai da leitura de neurônios do cérebro simulado.

## Estado

- [x] F0 reconhecimento e plano — `docs/F0_reconhecimento.md`
- [x] F1 dados → CSR, motor event-driven, validação açúcar→MN9, benchmark — `docs/F1_validacao.md`
- [x] F2 interface sensório-motora + SCREEN por sexo — `docs/F2_screen.md`
- [x] F3 mundo da superfície + replay + visualizador — `docs/F3_mundo.md`
- [x] F4 robôs, laboratório, segredos S1–S4, linha do tempo, diário — `docs/F4_lab.md`
- [ ] F5 painel do cérebro, câmeras, métricas, 100 dias

## Como rodar

Requisitos: Windows 11 (PowerShell), [uv](https://docs.astral.sh/uv/), Node 22+.
Sem GPU, sem Docker, sem WSL.

```powershell
uv sync                                   # Python 3.11 + dependências
uv run python scripts/download.py         # ~700 MB de dados (fora do git)
uv run matrix build-pack flywire          # FlyWire v783  -> data/packs/flywire783
uv run matrix build-pack malecns          # MaleCNS v1.0  -> data/packs/malecns10
uv run pytest                             # testes (inclui equivalência com Brian2)
uv run matrix validate --pack flywire783  # açúcar -> MN9, amargo reduz
uv run matrix bench --pack malecns10      # velocidade e memória
uv run matrix reduce --pack flywire783 --k 4   # subcircuito reduzido
uv run matrix screen --pack flywire783    # SCREEN: entradas x saidas por sexo
uv run matrix simulate --days 1 --seconds 60 --brain reduced   # um dia -> runs/day_0000
cd web; npm install; npm run dev          # visualizador em http://localhost:5173
```

## O que é real / o que é premissa nossa

| Real (vem dos dados ou da literatura) | Premissa nossa (escolha de projeto) |
|---|---|
| Fiação dos dois conectomas (quem conecta com quem, quantas sinapses) | Taxas sensoriais: como cada situação do mundo vira Hz de Poisson nas entradas |
| Sinal das sinapses (previsão de neurotransmissor por neurônio; Eckstein 2024) | Ganhos motores: como Hz nos neurônios descendentes vira velocidade, giro, salto |
| Dinâmica LIF e todos os seus parâmetros (Shiu 2024): V_rest = V_reset = −52 mV, limiar −45 mV, τ_m 20 ms, τ_syn 5 ms, refratário 2,2 ms, atraso 1,8 ms, 0,275 mV por sinapse, dt 0,1 ms | Corpo cinemático simplificado (sem física de pernas) |
| Dois detalhes do modelo publicado que não estão no artigo, mas estão no código e nos dados: (a) entrada que chega a um neurônio refratário é descartada (escrita condicional do Brian2); (b) neurônios estimulados por Poisson não têm refratário (`model.py`: `rfc = 0`). Com os dois, reproduzimos a simulação publicada dentro de 3 % (`docs/F1_validacao.md`) | Individualidade: semente, jitter lognormal de 5 % no ganho sináptico, ganho de fome |
| Rótulos de tipo celular usados para escolher entradas e saídas (tabelas oficiais; nenhum ID no código) | Feromônios e canção como concentrações e vibrações simplificadas |
| | Robôs (máquinas de estado sem IA), laboratório e os quatro segredos como mecanismos físicos (`world/world.yaml` → `lab`) |
| | Humor, pensamentos e gostos do visualizador são leituras do replay (sensores, estado, fome), não estados internos do cérebro |
| | Reutilização das constantes de Shiu (ajustadas ao FlyWire) no MaleCNS, com VNC incluído; taxas não são comparáveis entre os sexos |
| | Histamina tratada como inibitória e `unclear` como sem saída no MaleCNS |
| | Regra de sinal por neurônio (voto majoritário) ignora co-transmissão e receptores pós-sinápticos |
| Bistabilidade do modelo: com estímulo forte (≥ 62 GRNs a 100 Hz) um laço recorrente do lobo antenal e do corpo cogumelar se auto-sustenta; igual no Brian2 | Taxas sensoriais do mundo calibradas abaixo do limiar de ignição; o estado de "convulsão" é detectado e registrado, nunca escondido |
| 39 % (fêmea) e 33 % (macho) dos neurônios locais do lobo antenal têm previsão de NT excitatória, contra a literatura (GABA/Glu); Eckstein 2024 cita a classe como mal prevista | Correção de sinal: ALLN forçados a inibitórios nos dois sexos (`config.yaml`); no macho, monoaminas sem efeito rápido; tetos sensoriais por sexo. Tudo em `interventions` |
| Quais reflexos existem no LIF (SCREEN, `docs/F2_screen.md`): comer, fuga, marcha e giro por odor/objeto (fêmea), ré por toque (macho), canção fraca (macho) | Só esses entram no mundo (`reflexes_enabled`); sociais da fêmea, agressão, grooming e aceitação/rejeição são lacunas, não código |

Lacunas documentadas (F0): a fêmea não tem no cérebro os neurônios de contato de
feromônio (ppk23/ppk25) nem cerdas das pernas; o FlyWire não separa GRNs de água
dos de açúcar; aDN1, oDN1, BPN e neurônios de parada só têm rótulos comunitários
e entram apenas como candidatos até o SCREEN da F2. No MaleCNS os neurônios
sensoriais têm lado só por `rootSide`, e as populações são assimétricas nos dados
(ex.: ORN_DA1 105 D / 51 E / 48 sem lado).

## Estrutura

```
brain/      motor LIF event-driven, pacotes CSR, tipos, subcircuito, referência Brian2
interface/  (F2) sensorial, motor, config de ganhos
world/      (F3) terreno, objetos, robôs, segredos, física simples
replay/     (F3) formato de replay
web/        (F3) Vite + TypeScript + Three.js
scripts/    download, validação, benchmark, simulate_days
docs/       relatórios por fase
data/       dados baixados e pacotes (fora do git)
```

Ver `ATTRIBUTION.md` para fontes e licenças.
