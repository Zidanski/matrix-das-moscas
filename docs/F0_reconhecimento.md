# F0 — Reconhecimento, plano e riscos (2026-09-21)

Tudo abaixo vem de leitura direta das fontes citadas. Itens marcados
**[não verificado]** só serão confirmados ao abrir os arquivos na F1.
Nenhum ID de neurônio foi anotado aqui de propósito: IDs virão das tabelas.

## 1. Ambiente local (verificado)
- Windows 11 Pro, i5-8350U (4C/8T), 16 GB (5,7 GB livres no momento), UHD 620.
- uv 0.12.5 (Python 3.11.16 disponível para instalar); Node 24.19 (LTS, serve);
  git 2.55; **`gh` ausente; identidade git (user.name/email) não configurada**.
- Pasta C:\meuMundoNovo vazia; 143 GB livres em disco.

## 2. Fontes de dados escolhidas (nenhum download > 1 GB)

| Uso | Arquivo | Tamanho | Origem / licença |
|---|---|---|---|
| Fêmeas: arestas já assinadas, índice → root_id v783 | `Connectivity_783.parquet` + `Completeness_783.csv` | 101 MB + 3 MB | repo philshiu/Drosophila_brain_model (MIT; dados FlyWire CC-BY-4.0) |
| Fêmeas: tipos, lado, NT, soma | `Supplemental_file1_neuron_annotations.tsv` v3.1.0 | 32 MB | flyconnectome/flywire_annotations (sem LICENSE; cita Schlegel 2024, Dorkenwald 2024) |
| Machos: anotações | `body-annotations-male-cns-v1.0-minconf-0.5.feather` | 15 MB | gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/ (CC-BY 4.0, Berg et al. 2026 Cell) |
| Machos: neurotransmissor por neurônio | `body-neurotransmitters-male-cns-v1.0.feather` | 43 MB | idem |
| Machos: arestas (só corpos Traced) | `connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather` | 508 MB | idem |

Total ≈ 700 MB. Os arquivos de sinapses (6–13 GB) e o `connectome-weights` completo
(1,05 GB) **não** são necessários. Alternativa para FlyWire com limiar ≥ 5 sinapses:
`connections.csv.gz` (50 MB) do bucket público do Codex, mas o bucket é um espelho
não documentado; fica como opção de benchmark, não como fonte primária.

## 3. Modelo de Shiu et al. 2024 (conferido em model.py)
V_rest = V_reset = −52 mV; limiar −45 mV; τ_m 20 ms; τ_syn 5 ms; refratário 2,2 ms;
atraso 1,8 ms; w_syn 0,275 mV; Poisson 150 Hz (padrão) com peso 250·w_syn;
dt 0,1 ms (padrão Brian2); método `linear` (exato). GABA e glutamato inibem;
ACh, DA, 5-HT, OA excitam; sinal por neurônio (voto majoritário). **Sem limiar de
sinapses** no arquivo de Shiu (≈15 M arestas). Licença MIT.

Port MLX (Kisame76): MaleCNS filtrado por `superclass` não nulo e NT conhecido;
monoaminas viram 0 (difere de Shiu); ressalva explícita de que as constantes
foram ajustadas só ao FlyWire. fly-brain-minecraft: mesmo LIF, event-driven em
CPU, MaleCNS com ≥ 5 sinapses (6,3 M arestas), ganho global 0,65, dt 0,5 ms,
25–60 ms de CPU por 50 ms biológicos em 8 threads de um servidor de 32 núcleos.
Eon (loop 15 ms): lê DNa01/DNa02 (giro), oDN1 (velocidade), MN9, aDN (grooming),
GF; não cita MDN nem DNp09; mapeamento spike→motor escolhido "à mão".

## 4. Tipos celulares: o que existe em cada conectoma

Legenda: OK = rótulo formal; ~ = só rótulo comunitário/sinônimo ou não verificado; X = ausente.

| Função | FlyWire v783 (fêmea) | MaleCNS v1.0 (macho) |
|---|---|---|
| GRN açúcar | OK `LB3` (cell_sub_class `sugar/water`, 64/58) | OK `LB3b`, `LB3c` |
| GRN água | ~ não separada de açúcar (usa `LB3`) | ~ `LB3a` (segundo Kisame76) |
| GRN amargo | OK `LB1a,LB1d`, `LB1b`, `LB1c`, `LB1e` | ~ resolver via coluna `flywireType` |
| GRN pernas | OK `SA_VTV_1…10` (74, ascendentes) | OK `LgLG1a…LgLG8` (no VNC) |
| ppk23/ppk25 (contato feromônio) | X ausente no cérebro | OK `LgLG5`, `LgLG8` (ppk23+/25+), `LgLG6`, `LgLG7` — **no VNC** |
| ORN DM1 / V / DA2 | OK `ORN_DM1`, `ORN_V`, `ORN_DA2` | OK mesmos nomes |
| cVA: Or67d / Or65a | OK `ORN_DA1` (60/66), `ORN_DL3` | OK `ORN_DA1` (204), `ORN_DL3` |
| Audição JO-A / JO-B | OK `JO-A1…A5`, `JO-B1_a…B4_b` | OK mesmos (+ `-unclear`) |
| Cerdas das pernas | X (só cerdas da cabeça `BM_*`) | OK sensoriais de perna no VNC |
| Looming LC4 / LPLC2; LC11 | OK | OK |
| MN9 | OK `CB0701` (rótulo comunitário "MN9") | OK `MN9` |
| Fibra gigante | OK `DNp01` | OK `DNp01` |
| Marcha DNp09 (P9) | OK `DNp09` | OK `DNp09` |
| oDN1 / BPN | ~ comunitário: `DNg97` ("P9-oDN1"); BPN em `SMP461/459`, `CL210_a`, `CB4187` | ~ 404 pelo nome; buscar via `flywireType` |
| Giro DNa01 / DNa02 | OK | OK |
| Ré MDN | OK `MDN` (2/2) | OK `MDN` (4) |
| Grooming aDN1 | ~ só "putative aDN 2" em `DNge078` (aDN1 não achado) | ~ não achado |
| Parada (Brake/Foxglove/Bluebell) | ~ comunitário: `DNg60`, `CB0890`, `AN_GNG_53/54/76` | ~ não verificado |
| P1 (corte macho) | X (esperado) | OK `pC1_1a…pC1_19` (43 tipos macho-específicos) |
| pC1 | OK `pC1a…pC1e` (d/e fêmea-específicos) | OK `pC1x_b`, `pC1x_c` |
| Agressão fêmea aIPg | OK `aIPg1…4` (hemibrain_type) | OK `aIPg1,2,5,6,10` + `aIPg_m1…m4` |
| Agressão macho Tk / aSP2 | X | OK TkFruM = `AVLP727m`; aSP2 = família `SIP1xxm`/`SMP7xxm` |
| Canção pIP10 / vPR6 / dPR1 | X | OK `pIP10` (cérebro), `vPR6`, `dPR1` (**VNC**) |
| aSP22 / DNp13 | OK | OK (dimórficos) |
| Aceitação vpoDN | OK `DNp37` (hemibrain_type `vpoDN`) | — |
| Rejeição / ovipositor DNp13, oviDN | OK `DNp13`, `oviDNa_a/b`, `oviDNb` | `DNp13` |
| DA1_lPN | OK (8/7) | OK (13) |

Consequências para o desenho (decisões propostas):
1. **Machos mantêm o VNC** (166 k neurônios). O feromônio de contato, a canção
   (vPR6/dPR1) e as cerdas de perna vivem lá; sem VNC o núcleo social do macho some.
   Custo: ~1,7× o cérebro da fêmea. O benchmark decide se o "dia" longo usa o
   subcircuito reduzido.
2. **Fêmeas não têm sensor de contato de feromônio no cérebro.** Lacuna documentada:
   a fêmea sente cVA só pelo olfato (`ORN_DA1`/`ORN_DL3`) e o contato físico só via
   `SA_VTV_*` (gustação genérica de perna). Não vou fingir ppk23 na fêmea.
3. Água na fêmea é indistinguível de açúcar no FlyWire: o mundo estimula `LB3`
   para água também, com ganho menor, e o README declara isso.
4. aDN1, oDN1, BPN, halting: só rótulos comunitários. Entram no SCREEN como
   candidatos; se o screen não mostrar reflexo, viram lacuna.
5. Sinal do MaleCNS: mesma regra de Shiu (GABA/Glu −; ACh/DA/5-HT/OA +;
   histamina −; `unclear` = 0) para manter uma premissa só; ganho global
   configurável (fly-brain-minecraft usou 0,65) e registrado como premissa.

## 5. Arquitetura proposta (resumo)
- `brain/data`: leitura em chunks (pyarrow) → CSR de saída por conectoma em `.npz`
  (indptr int64, indices int32, w int8 = contagem assinada; multiplica por w_syn
  na hora). FlyWire ≈ 15 M arestas ≈ 75 MB; MaleCNS ≈ 25 M ≈ 125 MB. mmap.
- `brain/engine`: LIF event-driven em Numba. Estado só dos neurônios "ativos"
  (V ≠ V_rest ou g ≠ 0); anel de 18 slots (1,8 ms / 0,1 ms) para atrasos; entrada
  Poisson gerada por semente; integração exata (exponenciais) para bater com o
  `linear` do Brian2; refratário por contador. Nada de SpMV por passo.
- `brain/reduce`: subcircuito de k saltos = interseção de BFS a partir das
  entradas e BFS reversa a partir das saídas (reimplementação própria; ideia do
  connectome_interpreter, MIT).
- Validação F1: varredura de açúcar 10–200 Hz → MN9 sobe monotônico; amargo
  100 Hz + açúcar 100 Hz silencia MN9; JO-CE → aBN1/aDN1 vs JO-F (opcional);
  nos dois conectomas. Comparação com Brian2 no FlyWire (taxas médias, 5 trials).
- Individualidade: semente, jitter lognormal 5 % no ganho, ganho de fome; modo
  controle com embaralhamento preservando grau (in/out) por neurônio.
- 6 processos, 4 ativos por vez, janelas de 15 ms biológicos; replay gravado
  por "dia" e assistido depois no Vite + Three.js.

## 6. Riscos (ordem de gravidade)
1. **Velocidade nesta CPU.** Referência: 8 threads de servidor dão ~1× tempo real
   para 1 mosca com dt 0,5 ms. Aqui, com dt 0,1 ms e 1 thread por mosca, espere
   10–50× mais lento que o tempo real por mosca. Um dia de 60 s biológicos com 6
   moscas pode levar 1–3 h no cérebro completo. Mitigação: replay (já decidido),
   subcircuito reduzido como padrão, limiar de sinapses como opção rotulada.
2. **Brian2 no Windows** precisa de compilador C para o alvo Cython; o alvo
   numpy funciona sem compilador mas é lento (dezenas de minutos por trial).
   Mitigação: 5 trials de 1 s num só experimento, rodado uma vez e salvo.
3. **Constantes de Shiu no MaleCNS**: risco de silêncio ou explosão de atividade
   com o VNC junto. Mitigação: ganho global no arquivo de config, medido no
   benchmark, declarado como premissa.
4. **Reflexos que podem não existir no LIF sem ajuste**: closed-loop-fly relata
   que DNa02 mal lateraliza; Eon usa só 7–8 DNs. O SCREEN é o filtro; reflexos
   sociais ausentes viram lacuna, não código.
5. **RAM**: só 5,7 GB livres agora. Preparo dos CSR fica < 3 GB, mas os dias
   simulados pedem fechar outros programas.
6. **GitHub**: sem `gh` e sem identidade git. Preciso de usuário GitHub e do OK
   para instalar `gh` (winget) ou de um token; sem isso não crio o repositório.
7. Colunas exatas dos feathers do MaleCNS e o tipo do GRN amargo no macho
   **[não verificados]** até abrir os arquivos.
8. Licenças: fly-brain (Eon) é GPL-2.0, cocoa/coconatfly GPL-3 → não copiar
   código; só citar. Shiu, Kisame76, fly-brain-minecraft, connectome_interpreter
   são MIT.

## 7. Fase 1 (o que faço após o OK)
1. `uv init` com Python 3.11, pyproject, pytest, numba, numpy, pyarrow, pandas.
2. Scripts de download com verificação de tamanho; dados em `data/` (fora do git).
3. `brain/data`: FlyWire parquet → CSR; MaleCNS feathers → CSR (filtro Traced,
   VNC mantido, coluna `flywireType` preservada para o mapa de tipos).
4. Tabela de tipos → índices por sexo e lado (`brain/types.py`), gerada das
   anotações, sem IDs no código.
5. Motor event-driven + testes unitários (neurônio isolado, atraso, refratário,
   comparação com integração exata).
6. Validação açúcar/amargo → MN9 nos dois; Brian2 no FlyWire; benchmark de
   full vs reduzido vs limiar ≥ 5; relatório em `docs/F1_validacao.md`. PARE.
