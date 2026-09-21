# PROJETO: A MATRIX DAS MOSCAS

Um mundo 3D assumidamente falso, habitado por 6 Drosophilas (3 machos, 3
fêmeas) cujo comportamento sai de emulações de cérebro inteiro baseadas em
conectomas reais. Debaixo do mundo há um laboratório secreto operado por
robôs. Se as moscas descobrirem os segredos, escapam. Talvez nunca escapem.
Isso é o experimento, não um defeito.

## 0. Hardware alvo e consequências (já decididas, não reabra)
Windows 11 x64, Intel i5-8350U (4 núcleos / 8 threads), 16 GB RAM, Intel
UHD 620 (sem CUDA, sem MPS). Portanto:
- Motor em CPU: NumPy + Numba, EVENT-DRIVEN (propaga só as sinapses dos
  neurônios que dispararam no passo). Proibido SpMV por passo.
- 6 moscas = 6 processos, no máximo 4 ativos por vez (round-robin em
  janelas de 15 ms de tempo biológico). Conectividade em CSR aberta
  com mmap, uma cópia por conectoma (FlyWire e MaleCNS), compartilhada.
- Parquet/feather carregados em chunks (pyarrow), convertidos direto para
  CSR em disco. Pico < 6 GB no preparo, < 1,5 GB por processo.
- MODO REPLAY é o padrão: o mundo é simulado offline em "dias" (episódios
  de N segundos biológicos), gravado, e assistido depois a 60 fps.
- Python 3.11 com uv; Node 22 LTS; tudo roda em PowerShell, sem WSL/Docker.

## 1. Como trabalhar
- Fases (seção 10). Ao fim de cada fase rode os testes, mostre e PARE.
- Peça confirmação antes de qualquer download maior que 1 GB.
- NUNCA invente IDs de neurônios. Todo ID vem de tabela oficial. Se não
  achar um tipo celular em um dos conectomas, diga e proponha alternativa.
- Confira licença antes de copiar código. Prefira reimplementar e citar.
- Commits pequenos e frequentes.

## 2. Conceito e regra de ouro
O CÓDIGO DO MUNDO NUNCA MOVE UMA MOSCA. O mundo só (a) transforma a
situação física em estímulos sensoriais e (b) reage fisicamente ao que as
moscas fazem. Todo movimento sai da leitura de neurônios do cérebro
simulado. Não existe roteiro, não existe "missão" no código.

Premissa científica: esses cérebros não aprendem, não têm plasticidade e
não entendem regras. Só têm reflexos inatos, inclusive reflexos sociais
(corte, agregação, agressão, fuga). Todo segredo do laboratório precisa ser
um mecanismo que só reflexos coincidentes de várias moscas conseguem
disparar. Se nunca dispararem, o replay mostra isso e as estatísticas
contam.

## 3. Decisões tomadas (F0, 2026-09-21)
- Machos mantêm o VNC inteiro (feromônio de contato, canção e cerdas de perna
  vivem lá). Fêmeas não têm sensor de contato de feromônio no cérebro: lacuna
  documentada, sem simulação inventada. Água na fêmea estimula os mesmos GRNs
  de açúcar com ganho menor.
- Sinal das sinapses: regra de Shiu (GABA/Glu −; ACh e monoaminas +) nos dois
  conectomas; histamina − e `unclear` sem saída no MaleCNS.
- Motor replica a semântica do Brian2: entrada que chega a neurônio refratário
  é descartada (verificado experimentalmente; teste disparo a disparo).

## 4. Motor do cérebro
- LIF de Shiu et al. com TODOS os parâmetros (V_rest = V_reset = -52 mV,
  limiar -45 mV, tau_m 20 ms, tau_sin 5 ms, refratário 2,2 ms, atraso 1,8 ms,
  0,275 mV por sinapse, dt 0,1 ms; entrada como trem de Poisson).
- Event-driven: fila de eventos com atraso, CSR de saída, kernel Numba.
- FÊMEAS = FlyWire v783. MACHOS = MaleCNS v1.0 (cérebro + VNC).
  Constantes de Shiu ajustadas ao FlyWire e reutilizadas no MaleCNS como
  premissa; taxas não são comparáveis entre os sexos.
- Individualidade: semente própria, jitter lognormal de 5% no ganho
  sináptico, ganho de "fome". Nomes curtos e cor por mosca.
- CONTROLE: modo opcional com conectoma embaralhado preservando grau.
- Benchmark e subcircuito reduzido (k saltos das entradas às saídas).
  Rotular sempre no HUD.

## 5. Interface sensório-motora
Loop de 15 ms de tempo biológico; taxas lidas com janela exponencial de
50-100 ms. Todo ganho em UM arquivo de configuração comentado.
Entradas: gustação (açúcar, amargo, água), olfato (DM1, V, DA2), feromônios
(cVA via DA1/DL3; contato ppk23 só no macho), audição (JO-A/B), mecanossensação
(JO, cerdas), visão (LC4/LPLC2 looming, LC11 objetos pequenos).
Saídas: marcha (DNp09/oDN1), giro (DNa01/DNa02), comer (MN9), grooming (aDN),
ré (MDN), parada, fuga (DNp01), corte (P1/pC1, pIP10, vPR6), agressão
(Tk/aSP2 machos; aIPg/pC1d fêmeas), aceitação/rejeição (vpoDN, DNp13).
Antes de construir o mundo, rode o SCREEN por sexo. Só use no mundo reflexos
que o screen mostrar que existem; os ausentes viram lacuna documentada.

## 6-8. Mundo, laboratório, segredos (S1-S4), visual 3D
Ver docs/F0_reconhecimento.md e o README. Estética Teletubbies falsa; robôs
são máquinas de estado; segredos exigem coincidência de reflexos de 2+ moscas.

## 9. Honestidade científica
README com tabela "real / premissa"; métricas por dia; comparação com o modo
controle; ATTRIBUTION.md com todas as fontes e licenças.

## 10. Fases
F0 reconhecimento (feito). F1 dados, motor, validação, benchmark (feito).
F2 interface + SCREEN (feito). F3 mundo + replay + visualizador (feito). F4 robôs, laboratório,
segredos, linha do tempo, diário (feito). F5 painel do cérebro, câmeras, vídeo,
métricas, README final (feito); 100 dias em runs/cem via scripts/run_100_days.ps1 e
`uv run matrix report` para o relatório.

## 11. Estrutura e comandos
brain/ interface/ world/ replay/ web/ scripts/ docs/ tests/
`uv run matrix build-pack flywire|malecns`, `uv run matrix validate`,
`uv run matrix bench`, `uv run matrix reduce --k 4`, `uv run matrix screen`,
`uv run matrix simulate --days N --seconds S --brain reduced|full`, `uv run pytest`;
`npm run dev` em web/ (serve ../runs). Ganhos: interface/config.yaml; mundo: world/world.yaml.
Dados baixados ficam em data/ (fora do git).
