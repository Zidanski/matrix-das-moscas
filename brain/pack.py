"""Pacote de conectoma: CSR de saida em disco (mmap) + tabela de neuronios.

Formato em data/packs/<nome>/ :
  indptr.npy   int64  (N+1)
  indices.npy  int32  (E)   indice do neuronio pos-sinaptico
  weights.npy  int16  (E)   contagem de sinapses com sinal do pre (+ excita, - inibe)
  neurons.parquet           uma linha por neuronio (idx, id, type, side, ...)
  meta.json                 origem, contagens, regra de sinal, unidades do soma

Os arquivos .npy abrem com np.load(mmap_mode="r"): os 6 processos das moscas
compartilham as mesmas paginas do sistema operacional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PACKS_DIR = Path("data/packs")
SIDE_MAP = {"left": "L", "right": "R", "center": "M", "na": "?", "L": "L", "R": "R", "M": "M"}

# Regra de sinal (Shiu 2024): GABA e glutamato inibem; ACh e monoaminas excitam.
# Histamina (fotorreceptores, so no MaleCNS) tratada como inibitoria (receptores
# HisCl/ort sao canais de cloreto). 'unclear'/ausente = 0 (sem arestas de saida).
NT_SIGN = {
    "acetylcholine": 1, "ach": 1,
    "dopamine": 1, "da": 1,
    "octopamine": 1, "oct": 1,
    "serotonin": 1, "ser": 1,
    "gaba": -1,
    "glutamate": -1, "glut": -1,
    "histamine": -1,
}


def nt_sign(nt: object) -> int:
    if nt is None or (isinstance(nt, float) and np.isnan(nt)):
        return 0
    return NT_SIGN.get(str(nt).lower(), 0)


@dataclass
class ConnectomePack:
    name: str
    indptr: np.ndarray
    indices: np.ndarray
    weights: np.ndarray
    neurons: pd.DataFrame
    meta: dict

    @property
    def n(self) -> int:
        return len(self.indptr) - 1

    @property
    def n_edges(self) -> int:
        return int(self.indptr[-1])

    # ---- consultas de tipos (nunca IDs no codigo: sempre por rotulo) ----
    def select(self, label: str | Iterable[str], side: str | None = None,
               column: str = "type", startswith: bool = False) -> np.ndarray:
        """Indices dos neuronios cujo `column` bate com `label` (e lado, se dado).

        side: 'L', 'R', 'M' ou None (todos). startswith=True casa prefixo.
        """
        col = self.neurons[column].astype("string")
        labels = [label] if isinstance(label, str) else list(label)
        if startswith:
            mask = np.zeros(len(col), dtype=bool)
            for lab in labels:
                mask |= col.str.startswith(lab).fillna(False).to_numpy()
        else:
            mask = np.asarray(col.isin(labels).fillna(False).to_numpy(), dtype=bool).copy()
        if side is not None:
            mask &= (self.neurons["side"].to_numpy() == side)
        return np.flatnonzero(mask).astype(np.int32)

    def out_degree(self) -> np.ndarray:
        return np.diff(self.indptr)

    def in_degree(self) -> np.ndarray:
        return np.bincount(self.indices, minlength=self.n)

    # ---- persistencia ----
    @classmethod
    def load(cls, name: str, root: Path = PACKS_DIR, mmap: bool = True) -> "ConnectomePack":
        d = Path(root) / name
        mode = "r" if mmap else None
        return cls(
            name=name,
            indptr=np.load(d / "indptr.npy", mmap_mode=mode),
            indices=np.load(d / "indices.npy", mmap_mode=mode),
            weights=np.load(d / "weights.npy", mmap_mode=mode),
            neurons=pd.read_parquet(d / "neurons.parquet"),
            meta=json.loads((d / "meta.json").read_text(encoding="utf-8")),
        )

    def save(self, root: Path = PACKS_DIR) -> Path:
        d = Path(root) / self.name
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / "indptr.npy", np.ascontiguousarray(self.indptr, dtype=np.int64))
        np.save(d / "indices.npy", np.ascontiguousarray(self.indices, dtype=np.int32))
        np.save(d / "weights.npy", np.ascontiguousarray(self.weights, dtype=np.int16))
        self.neurons.to_parquet(d / "neurons.parquet", index=False)
        (d / "meta.json").write_text(json.dumps(self.meta, indent=2, ensure_ascii=False), encoding="utf-8")
        return d

    @classmethod
    def from_edges(cls, name: str, n: int, pre: np.ndarray, post: np.ndarray,
                   w: np.ndarray, neurons: pd.DataFrame | None = None, meta: dict | None = None) -> "ConnectomePack":
        """Monta um pacote a partir de listas de arestas (uso em testes e subcircuitos)."""
        pre = np.asarray(pre, dtype=np.int64)
        order = np.argsort(pre, kind="stable")
        counts = np.bincount(pre, minlength=n)
        indptr = np.zeros(n + 1, dtype=np.int64)
        np.cumsum(counts, out=indptr[1:])
        if neurons is None:
            neurons = pd.DataFrame({"idx": np.arange(n), "id": np.arange(n), "type": [""] * n, "side": ["?"] * n})
        return cls(name, indptr, np.asarray(post, dtype=np.int32)[order],
                   np.asarray(w, dtype=np.int16)[order], neurons, meta or {})


def csr_from_stream(n: int, batches: Iterable[tuple[np.ndarray, np.ndarray, np.ndarray]],
                    batches_again: Iterable[tuple[np.ndarray, np.ndarray, np.ndarray]] | None = None):
    """CSR em duas passadas sem carregar tudo: 1) graus de saida 2) preenchimento.

    `batches` e `batches_again` sao geradores das mesmas arestas (pre, post, w).
    Se `batches_again` for None, os lotes sao guardados em memoria na 1a passada.
    """
    counts = np.zeros(n, dtype=np.int64)
    kept = None if batches_again is not None else []
    for pre, post, w in batches:
        counts += np.bincount(pre, minlength=n)
        if kept is not None:
            kept.append((pre, post, w))
    indptr = np.zeros(n + 1, dtype=np.int64)
    np.cumsum(counts, out=indptr[1:])
    e = int(indptr[-1])
    indices = np.empty(e, dtype=np.int32)
    weights = np.empty(e, dtype=np.int16)
    cursor = indptr[:-1].copy()
    src = kept if kept is not None else batches_again
    for pre, post, w in src:
        # posicao de cada aresta: cursor[pre] + rank dentro do lote
        order = np.argsort(pre, kind="stable")
        pre_s, post_s, w_s = pre[order], post[order], w[order]
        uniq, start, cnt = np.unique(pre_s, return_index=True, return_counts=True)
        pos = np.repeat(cursor[uniq], cnt) + (np.arange(len(pre_s)) - np.repeat(start, cnt))
        indices[pos] = post_s
        if np.any(np.abs(w_s) > 32767):
            raise ValueError("peso excede int16")
        weights[pos] = w_s
        cursor[uniq] += cnt
    assert np.array_equal(cursor, indptr[1:])
    return indptr, indices, weights
