"""Decodificador motor: contagens por populacao -> taxas (janela exponencial) -> comandos.

Nada aqui move a mosca por conta propria: cada comando e uma funcao das
taxas lidas nos neuronios de saida, com ganhos do config.yaml. Reflexos que o
SCREEN nao confirmar ficam desligados (`enabled` no MotorDecoder).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from brain.pack import ConnectomePack
from brain.types import populations, OUTPUTS


@dataclass
class MotorState:
    forward_cm_s: float = 0.0
    turn_rad_s: float = 0.0
    backward_cm_s: float = 0.0
    feed: bool = False
    groom: bool = False
    halt: bool = False
    jump: bool = False
    court: bool = False
    song: bool = False
    aggression: bool = False
    accept: bool = False
    reject: bool = False
    rates_hz: dict = field(default_factory=dict)   # por populacao e lado, para HUD/replay


class RateReader:
    """Taxas por populacao (E, D, total) com janela exponencial de tau ms."""

    def __init__(self, pack: ConnectomePack, names: list[str], tau_ms: float):
        allp = populations(pack)
        sides = pack.neurons["side"].to_numpy()
        self.groups: dict[str, dict[str, np.ndarray]] = {}
        for n in names:
            idx = allp.get(n, np.zeros(0, np.int32))
            if len(idx) == 0:
                continue
            self.groups[n] = {"L": idx[sides[idx] == "L"], "R": idx[sides[idx] == "R"], "all": idx}
        self.tau_ms = tau_ms
        self.rates: dict[str, dict[str, float]] = {n: {"L": 0.0, "R": 0.0, "all": 0.0} for n in self.groups}
        self._last_counts = None

    def update(self, counts: np.ndarray, dt_ms: float) -> dict:
        """counts = contagem cumulativa por neuronio (engine.counts)."""
        if self._last_counts is None:
            self._last_counts = counts.copy()
            return self.rates
        d = counts - self._last_counts
        self._last_counts = counts.copy()
        a = float(np.exp(-dt_ms / self.tau_ms))
        for n, g in self.groups.items():
            for side, idx in g.items():
                if len(idx) == 0:
                    continue
                inst = d[idx].sum() / len(idx) / (dt_ms / 1000.0)   # Hz por neuronio nesta janela
                self.rates[n][side] = a * self.rates[n][side] + (1 - a) * inst
        return self.rates

    def reset(self):
        self._last_counts = None
        for n in self.rates:
            self.rates[n] = {"L": 0.0, "R": 0.0, "all": 0.0}


class MotorDecoder:
    def __init__(self, pack: ConnectomePack, cfg: dict, sex: str, enabled: set[str] | None = None):
        self.cfg = cfg["motor"]
        self.sex = sex
        self.reader = RateReader(pack, OUTPUTS, cfg["loop"]["rate_tau_ms"])
        # por padrao tudo ligado; o SCREEN (F2) define o conjunto real por sexo
        self.enabled = set(self.cfg.keys()) if enabled is None else set(enabled)

    def _rate(self, pops, side="all") -> float:
        return float(sum(self.reader.rates[p][side] for p in pops if p in self.reader.rates))

    def _peak(self, pops) -> float:
        """Lado mais forte: reflexos por limiar sao unilaterais (ex.: MN9 D com acucar D)."""
        return max(self._rate(pops, "L"), self._rate(pops, "R"), self._rate(pops, "all"))

    def decode(self, counts: np.ndarray, dt_ms: float) -> MotorState:
        r = self.reader.update(counts, dt_ms)
        c = self.cfg
        m = MotorState(rates_hz={n: dict(v) for n, v in r.items()})
        if "forward" in self.enabled:
            m.forward_cm_s = min(c["forward"]["max_cm_s"], c["forward"]["gain_cm_s_per_hz"] * self._rate(c["forward"]["pops"]))
        if "turn" in self.enabled:
            diff = self._rate(c["turn"]["pops"], "L") - self._rate(c["turn"]["pops"], "R")
            m.turn_rad_s = float(np.clip(c["turn"]["gain_rad_s_per_hz"] * diff, -c["turn"]["max_rad_s"], c["turn"]["max_rad_s"]))
        if "backward" in self.enabled and self._peak(c["backward"]["pops"]) > c["backward"]["threshold_hz"]:
            m.backward_cm_s = c["backward"]["gain_cm_s_per_hz"] * self._peak(c["backward"]["pops"])
        for key, attr in [("feed", "feed"), ("groom", "groom"), ("halt", "halt"), ("jump", "jump"),
                          ("accept", "accept"), ("reject", "reject")]:
            if key in self.enabled and key in c and self._peak(c[key]["pops"]) > c[key]["threshold_hz"]:
                setattr(m, attr, True)
        if self.sex == "male":
            if "court" in self.enabled and self._peak(c["court"]["pops"]) > c["court"]["threshold_hz"]:
                m.court = True
            if "song" in self.enabled and self._peak(c["song"]["pops"]) > c["song"]["threshold_hz"]:
                m.song = True
            if "aggression_male" in self.enabled and self._peak(c["aggression_male"]["pops"]) > c["aggression_male"]["threshold_hz"]:
                m.aggression = True
        else:
            if "aggression_female" in self.enabled and self._peak(c["aggression_female"]["pops"]) > c["aggression_female"]["threshold_hz"]:
                m.aggression = True
        return m
