# Atribuições e licenças

Este projeto reimplementa modelos publicados e usa dados públicos. Nada aqui é
original em ciência; o que é nosso está listado no README como "premissa".

## Dados

| Recurso | Uso | Licença | Citação |
|---|---|---|---|
| FlyWire v783 (conectividade; arestas assinadas por Shiu et al.) | cérebro das fêmeas | CC-BY-4.0 (dados FlyWire) | Dorkenwald S. et al. *Neuronal wiring diagram of an adult brain.* Nature 634, 124–138 (2024). doi:10.1038/s41586-024-07558-y |
| FlyWire annotations v3.1.0 (flyconnectome/flywire_annotations) | tipos, lado, NT, soma das fêmeas | sem LICENSE no repo; autores pedem citação | Schlegel P. et al. *Whole-brain annotation and multi-connectome cell typing of Drosophila.* Nature 634, 139–152 (2024). doi:10.1038/s41586-024-07686-5 |
| Previsão de neurotransmissores (embutida nas anotações e nos sinais de Shiu) | sinal das sinapses | — | Eckstein N. et al. *Neurotransmitter classification from electron microscopy images at synaptic sites in Drosophila melanogaster.* Cell 187, 2574–2594 (2024). doi:10.1016/j.cell.2024.03.016 |
| MaleCNS v1.0 (body-annotations, body-neurotransmitters, connectome-weights traced-only) | cérebro + VNC dos machos | CC-BY 4.0 | Berg S. et al. *Sexual dimorphism in the complete Drosophila male central nervous system connectome.* Cell 189(18), 5504–5526 (2026). doi:10.1016/j.cell.2026.08.015 |

## Modelo

| Recurso | Uso | Licença |
|---|---|---|
| Shiu P.K. et al. *A Drosophila computational brain model reveals sensorimotor processing.* Nature 634, 210–219 (2024). doi:10.1038/s41586-024-07763-9 — github.com/philshiu/Drosophila_brain_model | equações e todos os parâmetros do LIF; arquivo Connectivity_783.parquet | MIT (código) |
| Eon Systems, *Embodied brain emulation* (eon.systems/updates/embodied-brain-emulation, 2026) e github.com/eonsystemspbc/fly-brain | referência do loop de 15 ms e dos neurônios descendentes lidos; nenhum código copiado | GPL-2.0-or-later (não copiado) |
| github.com/Kisame76/drosophila-brain-mlx | referência de como filtrar o MaleCNS e ressalva das constantes; nenhum código copiado | MIT |
| github.com/blendi-remade/fly-brain-minecraft | referência do esquema event-driven em CPU; nenhum código copiado | MIT |
| github.com/YijieYin/connectome_interpreter | ideia do subcircuito por saltos; reimplementado | MIT |
| github.com/flyconnectome/cocoa, github.com/natverse/coconatfly | referência de correspondência de tipos; usamos a coluna `flywireType` do próprio MaleCNS | GPL-3.0 (não copiado) |
| Brian2 (Stimberg, Brette, Goodman 2019, eLife) | referência de validação nos testes | CeCILL 2.1 |

## Bibliotecas

NumPy (BSD-3), Numba (BSD-2), pyarrow (Apache-2.0), pandas (BSD-3), SciPy (BSD-3),
psutil (BSD-3), pytest (MIT), Three.js (MIT), Vite (MIT), TypeScript (Apache-2.0).
