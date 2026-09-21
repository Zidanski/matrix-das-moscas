"""Codificador sensorial: situacao do mundo -> taxas de Poisson por neuronio.

Entrada: `SensoryState`, um dicionario {nome_da_populacao: (esq, dir)} com
valores em [0, 1] (0 = nada; 1 = estimulo maximo). Saida: (indices, taxas Hz).

Regras (config.yaml): rate = max_hz * clip(valor, 0, 1) ** gamma; max_hz pode
ser um numero ou {female: X, male: Y} (limiares de ignicao diferem por sexo).
Populacoes sem lado anotado ('?') recebem a media dos dois lados.
Populacoes ausentes no conectoma (ex.: ppk23 na femea) sao ignoradas e
listadas em `missing` - lacuna documentada, nunca inventada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from brain.pack import ConnectomePack
from brain.types import populations, INPUTS

SensoryState = dict[str, tuple[float, float]]


@dataclass
class SensoryEncoder:
    pack: ConnectomePack
    cfg: dict
    hunger_gain: float = 1.0
    pops: dict = field(default_factory=dict)
    missing: list = field(default_factory=list)

    def __post_init__(self):
        allp = populations(self.pack)
        self.pops = {}
        for name in INPUTS:
            if name not in self.cfg["sensory"]:
                continue
            idx_all = allp.get(name, np.zeros(0, np.int32))
            if len(idx_all) == 0:
                self.missing.append(name)
                continue
            sides = self.pack.neurons["side"].to_numpy()[idx_all]
            self.pops[name] = {
                "L": idx_all[sides == "L"], "R": idx_all[sides == "R"],
                "?": idx_all[(sides != "L") & (sides != "R")],
            }

    def rates_for(self, name: str, left: float, right: float) -> tuple[np.ndarray, np.ndarray]:
        c = self.cfg["sensory"][name]
        g = float(c.get("gamma", 1.0))
        mx = c["max_hz"]
        if isinstance(mx, dict):   # maximo por sexo: {female: X, male: Y}
            mx = mx[self.pack.meta.get("sex", "female")]
        mx = float(mx)
        if name in ("sugar", "water"):
            mx *= self.hunger_gain
        rl = mx * float(np.clip(left, 0, 1)) ** g
        rr = mx * float(np.clip(right, 0, 1)) ** g
        p = self.pops[name]
        idx = np.concatenate([p["L"], p["R"], p["?"]])
        rate = np.concatenate([np.full(len(p["L"]), rl), np.full(len(p["R"]), rr), np.full(len(p["?"]), 0.5 * (rl + rr))])
        return idx, rate

    def encode(self, state: SensoryState) -> tuple[np.ndarray, np.ndarray]:
        """Uniao de todas as populacoes com taxa > 0 (indices, Hz)."""
        idxs, rates = [], []
        for name, (l, r) in state.items():
            if name not in self.pops or (l <= 0 and r <= 0):
                continue
            i, rt = self.rates_for(name, l, r)
            m = rt > 0
            idxs.append(i[m]); rates.append(rt[m])
        if not idxs:
            return np.zeros(0, np.int32), np.zeros(0)
        idx = np.concatenate(idxs).astype(np.int32)
        rate = np.concatenate(rates)
        # um neuronio em duas populacoes (ex.: sugar e water na femea): soma das taxas
        if len(np.unique(idx)) != len(idx):
            u, inv = np.unique(idx, return_inverse=True)
            rate = np.bincount(inv, weights=rate)
            idx = u.astype(np.int32)
        return idx, rate
