# F2 — Interface sensório-motora e SCREEN por sexo (2026-09-21)

Dados brutos em `docs/F2_screen/`. Tudo aqui é medido com o config atual
(`interface/config.yaml`), que é o único lugar com ganhos e é todo premissa.

## 1. O que foi construído

- `interface/config.yaml`: loop de 15 ms, janela exponencial de 75 ms, limiar
  de ignição, ganhos por sexo (global, células de Kenyon, pré-sináptico por
  neurotransmissor, correção de sinal por classe), tetos sensoriais por
  população (e por sexo quando preciso), mapeamento motor por população, e o
  histórico de intervenções do laboratório.
- `interface/sensory.py`: situação do mundo `{população: (esq, dir)}` em [0, 1]
  → taxas de Poisson por neurônio, por lado. Populações ausentes num conectoma
  ficam em `missing` (ppk23 na fêmea).
- `interface/motor.py`: contagens por população → taxas E/D/total com janela
  exponencial → `MotorState` (marcha, giro, ré, comer, grooming, parada, salto,
  corte, canção, agressão, aceitar, rejeitar). Reflexos por limiar usam o lado
  mais forte. Só entram no mundo os reflexos habilitados por sexo (seção 5).
- `interface/fly_brain.py`: uma mosca = cérebro + codificador + decodificador;
  identidade (nome, sexo, cor, semente, fome, controle); jitter lognormal de
  5 % no ganho por neurônio; detecção de ignição por janela.
- `brain/engine.py`: ganho pré-sináptico por neurônio (permite zerar as saídas
  rápidas de um neurotransmissor ou inverter o sinal de uma classe).
- Scripts: `screen.py`, `ignition_threshold.py`, `interventions.py`,
  `calibrate_gain.py`. CLI: `matrix screen`, `matrix calibrate-gain`.
- Testes: 24 passam (6 novos da interface, com pacote sintético).

## 2. O problema central: ignição, e o que a causa

A F1 mostrou que estímulos fortes acendem um laço auto-sustentado. A F2 mediu
o limiar de ignição de cada entrada (`*_ignition.csv`) e localizou os
disparadores olhando os tipos que explodem no início:

| Sexo | Sem intervenção | Disparador (tipos no início da ignição) |
|---|---|---|
| Fêmea | ORN_DM1 ignita a **5 Hz**; V e DA1 a 20 Hz; DL3 a 40 Hz; gustação, audição e visão estáveis até 60–80 Hz | ORNs de outros glomérulos + neurônios locais do lobo antenal (`lLN1_bc`, `lLN2X12`, `lLN2P`) previstos como ACh/dopamina/serotonina → células de Kenyon |
| Macho | quase tudo ignita a 10 Hz (ORNs, pernas, JO-CE, LC4); açúcar a 20 Hz | (a) mesmos LNs do lobo antenal; (b) PAM dopaminérgicos → Kenyon; (c) cVA: laço no **VNC** (DLMn, dMS2, vMS12, w-cHIN = circuito de asa/voo) |

Diagnóstico: 166 dos 429 neurônios locais do lobo antenal da fêmea (39 %) e
139 dos 420 do macho estão excitatórios no modelo, quando a literatura os
descreve como GABA/glutamato quase todos. Eckstein et al. 2024 citam
explicitamente "LNs do lobo antenal previstos como serotonina" como falha da
previsão. Nenhuma intervenção genérica (ganho global 0,7, ganho 0,25 nas
Kenyon, monoaminas sem saída) resolveu o olfato; o ganho global 0,7 ainda
matava açúcar → MN9.

Intervenções adotadas (todas no `config.yaml`, seção `interventions`):

1. **ALLN → inibitório** (classe `cell_class == ALLN`, sinal das saídas forçado
   a −1) nos dois sexos. Efeito: fêmea estável até 80 Hz em todas as 15
   entradas; açúcar → MN9 preservado; surge um reflexo olfativo de marcha.
2. **Macho: dopamina, octopamina e serotonina sem saída rápida** (como no port
   de Kisame76). Efeito: açúcar 50 Hz passa de ignição em 1/2 e MN9 3,5 Hz para
   0/2 e MN9 33 Hz. Na fêmea a mesma regra mata açúcar → MN9 (via monoaminérgica
   validada por Shiu), portanto não se aplica a ela.
3. **Tetos sensoriais por sexo** a ~70 % do máximo estável: macho `leg_grn` 5 Hz
   (338 neurônios), `orn_v` 7, `orn_da1` 7, `jo_ce` 7, `bitter` 30, `orn_da2` 30.
   O laço do VNC do macho (cVA a ≥ 20 Hz) não tem correção principiada: fica o
   teto e a detecção de ignição.

Limiares depois das intervenções (`flywire783_ignition.csv`,
`malecns10_ignition.csv`): fêmea, nenhuma entrada ignita até 80 Hz; macho,
estável até 80 Hz em açúcar, água, ppk23, DM1, DL3, JO-A/B, LC4; limites em
bitter 40, DA2 40, LPLC2/LC11 60, V/DA1/JO-CE 10, pernas < 10.

## 3. SCREEN da fêmea (FlyWire v783, 2 sementes, 600 ms de estímulo unilateral no teto do config)

Nenhuma ignição em 36 condições. Taxas médias no último terço (Hz por neurônio):

| Entrada (lado) | Saídas que respondem |
|---|---|
| açúcar E / D | MN9 65 / 16; parada (candidatos DNg60/CB0890) 16 / 3 |
| água E | MN9 37 (mesmos GRNs; lacuna do FlyWire) |
| açúcar + amargo D | MN9 **0** (amargo anula) |
| amargo, DA2, DL3, JO-A, JO-CE, gustação de perna D | nada nas saídas lidas |
| gustação de perna E | oDN1 4, DNa01 1 (fraco) |
| ORN_DM1 (comida) E / D | oDN1 13 / 15, DNa02 13 / 9, DNa01 10 / 8 |
| ORN_V (CO2) E | DNa01 2, DNa02 2, oDN1 2 (fraco) |
| cVA (DA1) E / D | DA1_lPN 8 / 11; **nada** em pC1, aIPg, vpoDN, DNp13 (nem a 80 Hz bilateral) |
| canção (JO-B) D | GF 1; a 80 Hz bilateral GF 43 (sobressalto) |
| LC4 E / D | GF 49 / 49, DNa01 11 / 7, DNa02 6 / 4 |
| LPLC2 E / D | GF 84 / 92, oDN1 12 / 7, DNa01 11 / 7, DNa02 10 / 18 |
| LC11 E / D | DNa02 4 / 5, oDN1 0 / 11 |
| looming bilateral | GF 135, MDN 1 |
| cVA + canção + LC11 (80 Hz) | oDN1 35, DNa02 45, DA1_lPN 51, GF 7–12 |

DNp09 nunca dispara; oDN1 (rótulo comunitário) é o descendente de marcha
efetivo. aDN (grooming, candidato) nunca dispara com JO-CE: lacuna.

## 4. SCREEN do macho (MaleCNS v1.0 com VNC, 2 sementes, 600 ms, tetos do config)

Ignição só em LPLC2 E a 60 Hz e looming bilateral (por isso os tetos de LC4/LPLC2
do macho caíram para 40/30 Hz). Taxas médias (Hz por neurônio):

| Entrada (lado) | Saídas que respondem |
|---|---|
| açúcar D / E | MN9 19 / 5; E também MDN 8, oDN1 3 |
| açúcar + amargo D | MN9 **0** (amargo anula); MDN 9 |
| água, amargo, pernas, DA2, DL3, JO-A D, JO-B D, LC11 E | nada |
| ppk23 (contato) E | DNa02 2 (fraco); D nada |
| ORN_DM1 E / D | MDN 1 / 6, DNa01 1 / 3, oDN1 1 / 2 (fraco) |
| ORN_V D (CO2) | MDN 10, DNa02 3 |
| cVA (DA1) D | MN9 8, DA1_lPN 5 |
| JO-A E / JO-B E / JO-CE E (antena tocada) | **MDN 13 / 12 / 18** (ré); JO-B E também GF 27 |
| JO-CE D | MN9 6, MDN 5, pIP10 3 |
| LC4 E / D | GF 140 / 147, DNa01 11 / 0 |
| LPLC2 D | GF 152, MDN 3, pC1 3 |
| LC11 D | pIP10 4, MDN 2, P1 1 |
| cVA + ppk23 D | MN9 3 |
| cVA + canção D | MN9 2, MDN 1 |
| cVA + LC11 D | **DNp13 15, MN9 10, pIP10 6, aSP22 4, pC1 3**, MDN 2 |

Observações: MN9 D não responde a nada de E e vice-versa com força igual; os
sensoriais do macho são assimétricos nos dados. Marcha (oDN1/DNp09) é fraca
no macho (≤ 3 Hz). P1 (corte) quase não dispara (1 Hz); o descendente de
canção pIP10 responde a objeto pequeno + cVA (6 Hz). Tk (agressão) nunca
dispara. DNp13 (no macho, função incerta) responde forte a cVA + objeto
pequeno.

## 5. Reflexos habilitados por sexo (config `reflexes_enabled`)

| Reflexo | Fêmea | Macho | Evidência do SCREEN |
|---|---|---|---|
| comer (MN9) | sim | sim | açúcar 65/19 Hz; amargo anula |
| salto/fuga (GF) | sim | sim | looming 49–152 Hz; fêmea: canção forte também dá GF |
| marcha (oDN1 + DNp09) | sim | sim (fraco) | fêmea: odor de comida 13–15 Hz, LC11 11 Hz; macho ≤ 3 Hz |
| giro (DNa02 − DNa01) | sim | sim (fraco) | fêmea: odor 9–13 Hz por lado, looming; macho 1–3 Hz |
| ré (MDN) | não (1 Hz) | sim | macho: toque na antena/JO 12–18 Hz, CO2 10 Hz |
| parada (candidatos) | sim | não | fêmea: açúcar E 16 Hz |
| corte + canção (P1, pIP10) | — | sim (fraco) | pIP10 6 Hz com cVA + objeto pequeno; P1 1 Hz |
| grooming (aDN candidato) | não | não | nunca dispara |
| agressão (aIPg / Tk) | não | não | nunca disparam |
| aceitação (vpoDN) / rejeição (DNp13) | não | — | vpoDN nunca; DNp13 na fêmea 1 Hz com looming |

## 6. Lacunas documentadas (para o README e o diário)

1. Reflexos sociais da fêmea (pC1, aIPg, vpoDN, DNp13) não aparecem no LIF com
   cVA, canção, contato ou combinações, mesmo a 80 Hz bilateral: a fêmea deste
   mundo não aceita, não rejeita e não briga. Só percebe cVA em segunda ordem
   (DA1_lPN) e anda/gira para objeto pequeno + odor.
2. Agressão do macho (Tk/aSP2) nunca dispara. Corte é fraca (pIP10 6 Hz).
3. Grooming: o candidato comunitário aDN não responde a JO-CE em nenhum sexo.
4. ppk23 no macho só dá DNa02 2 Hz: o feromônio de contato quase não age.
5. Marcha do macho é fraca; o macho anda pouco por reflexo próprio.
6. Sem correção principiada para o laço do VNC do macho: tetos e detecção.
7. Todas as intervenções (ALLN, monoaminas do macho, tetos) são premissas
   registradas em `config.yaml` → `interventions`.

Consequência para os segredos: S2 (canção perto da porta com fêmea atrás)
depende de pIP10 fraco; S4 (agregação por feromônio) não tem reflexo de
agregação confirmado. O replay vai mostrar isso e as estatísticas vão contar.
