"""Modo CONTROLE: conectoma embaralhado preservando grau.

Troca os alvos pos-sinapticos entre pares de arestas escolhidos ao acaso
(Maslov-Sneppen sem rejeicao). Preserva exatamente: grau de saida de cada
neuronio, grau de entrada de cada neuronio (o multiconjunto de alvos nao muda),
e a distribuicao de pesos/sinais de cada linha (o peso fica com a aresta).
Destroi: quem fala com quem. Uma mosca com este cerebro serve de comparacao
nas estatisticas do mundo.
"""

from __future__ import annotations

import numpy as np
from numba import njit

from .pack import ConnectomePack


@njit(cache=True)
def _swap_targets(indices, n_swaps, seed):
    np.random.seed(seed)
    e = indices.shape[0]
    for _ in range(n_swaps):
        a = np.random.randint(0, e)
        b = np.random.randint(0, e)
        t = indices[a]
        indices[a] = indices[b]
        indices[b] = t


def shuffled_pack(pack: ConnectomePack, seed: int, swaps_per_edge: float = 3.0) -> ConnectomePack:
    indices = np.array(pack.indices, dtype=np.int32, copy=True)
    n_swaps = int(swaps_per_edge * len(indices))
    _swap_targets(indices, n_swaps, int(seed))
    meta = dict(pack.meta)
    meta.update({"control_shuffled": True, "shuffle_seed": int(seed), "shuffled_from": pack.name,
                 "hud_label": f"CONTROLE: conectoma embaralhado (semente {seed})"})
    return ConnectomePack(f"{pack.name}_shuffled{seed}", np.array(pack.indptr), indices,
                          np.array(pack.weights), pack.neurons.copy(), meta)
