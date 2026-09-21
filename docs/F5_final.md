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

## 3. Resultado dos 100 dias

(preenchido por `docs/F5_relatorio/relatorio.md` quando `runs/cem/log.txt`
terminar com `FIM`; ver a seção 4 do README)
