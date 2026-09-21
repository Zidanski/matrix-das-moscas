"""Subcircuito reduzido: neuronios a ate k saltos entre entradas e saidas.

Mantem o neuronio n se existe caminho entrada -> ... -> n -> ... -> saida com
comprimento total <= k (d_in(n) + d_out(n) <= k), mais todas as entradas e
saidas. Arestas entre neuronios mantidos sao preservadas com o mesmo peso.
Ideia inspirada em connectome_interpreter (MIT); reimplementado com BFS em CSR.

Rotular sempre no HUD: "cerebro reduzido k=N (M neuronios)".
"""

from __future__ import annotations

import numpy as np

from .pack import ConnectomePack


def _bfs_dist(indptr: np.ndarray, indices: np.ndarray, seeds: np.ndarray, k: int, n: int) -> np.ndarray:
    dist = np.full(n, k + 1, dtype=np.int32)
    frontier = np.unique(seeds)
    dist[frontier] = 0
    for d in range(1, k + 1):
        if len(frontier) == 0:
            break
        starts = indptr[frontier]
        ends = indptr[frontier + 1]
        lens = ends - starts
        tot = int(lens.sum())
        if tot == 0:
            break
        pos = np.repeat(starts - np.cumsum(lens) + lens, lens) + np.arange(tot)
        nbrs = np.unique(indices[pos])
        nbrs = nbrs[dist[nbrs] > d]
        dist[nbrs] = d
        frontier = nbrs
    return dist


def transpose_csr(indptr: np.ndarray, indices: np.ndarray, n: int):
    """CSC (arestas de entrada) a partir do CSR de saida, sem pesos."""
    src = np.repeat(np.arange(n, dtype=np.int32), np.diff(indptr))
    order = np.argsort(indices, kind="stable")
    t_indices = src[order]
    counts = np.bincount(indices, minlength=n)
    t_indptr = np.zeros(n + 1, dtype=np.int64)
    np.cumsum(counts, out=t_indptr[1:])
    return t_indptr, t_indices


def reduce_pack(pack: ConnectomePack, inputs: np.ndarray, outputs: np.ndarray, k: int,
                name: str | None = None, min_syn: int = 1) -> ConnectomePack:
    n = pack.n
    indptr = np.asarray(pack.indptr)
    indices = np.asarray(pack.indices)
    d_in = _bfs_dist(indptr, indices, np.asarray(inputs), k, n)
    t_indptr, t_indices = transpose_csr(indptr, indices, n)
    d_out = _bfs_dist(t_indptr, t_indices, np.asarray(outputs), k, n)
    keep = (d_in.astype(np.int64) + d_out.astype(np.int64)) <= k
    keep[np.asarray(inputs)] = True
    keep[np.asarray(outputs)] = True
    old = np.flatnonzero(keep)
    new_of_old = np.full(n, -1, dtype=np.int64)
    new_of_old[old] = np.arange(len(old))
    # arestas mantidas
    src = np.repeat(np.arange(n, dtype=np.int64), np.diff(indptr))
    w = np.asarray(pack.weights)
    m = keep[src] & keep[indices] & (np.abs(w) >= min_syn)
    pre = new_of_old[src[m]]
    post = new_of_old[indices[m]]
    neurons = pack.neurons.iloc[old].reset_index(drop=True).copy()
    neurons["idx_full"] = neurons["idx"].to_numpy()
    neurons["idx"] = np.arange(len(old), dtype=np.int32)
    meta = dict(pack.meta)
    meta.update({
        "reduced_from": pack.name, "k": int(k), "n_full": int(n), "n_neurons": int(len(old)),
        "n_edges": int(m.sum()), "min_syn": int(min_syn),
        "hud_label": f"cerebro reduzido k={k} ({len(old)} de {n} neuronios)",
    })
    sub = ConnectomePack.from_edges(name or f"{pack.name}_k{k}", len(old), pre, post, w[m], neurons, meta)
    return sub
