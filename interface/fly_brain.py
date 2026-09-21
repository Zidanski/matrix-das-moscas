"""Uma mosca = um cerebro + codificador sensorial + decodificador motor.

Loop: a cada `dt_ms` (15 ms biologicos) o mundo entrega um SensoryState, o
cerebro roda 150 passos de 0,1 ms com Poisson nas entradas, e o decodificador
devolve um MotorState. Individualidade: semente propria, jitter lognormal no
ganho sinaptico por neuronio, ganho global por sexo, ganho opcional nas
celulas de Kenyon e ganho de fome (multiplica acucar/agua).
Deteccao de ignicao: disparos na ultima janela acima do limiar do config.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from brain.engine import LIFEngine
from brain.pack import ConnectomePack
from brain.types import populations
from .config import load_config
from .motor import MotorDecoder, MotorState
from .sensory import SensoryEncoder, SensoryState


@dataclass
class FlyIdentity:
    name: str
    sex: str            # 'female' | 'male'
    color: str
    seed: int
    hunger_gain: float = 1.0
    control: bool = False   # conectoma embaralhado


def make_gain(pack: ConnectomePack, sex: str, cfg: dict, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    sigma = float(cfg["brain"]["jitter_lognormal_sigma"])
    gain = rng.lognormal(0.0, sigma, pack.n) if sigma > 0 else np.ones(pack.n)
    gain *= float(cfg["brain"]["global_gain"][sex])
    kcg = float(cfg["brain"]["kc_gain"][sex])
    if kcg != 1.0:
        kc = populations(pack).get("kc", np.zeros(0, np.int32))
        gain[kc] *= kcg
    return gain


class FlyBrain:
    def __init__(self, pack: ConnectomePack, identity: FlyIdentity, cfg: dict | None = None,
                 enabled_reflexes: set[str] | None = None):
        self.cfg = cfg or load_config()
        self.id = identity
        self.pack = pack
        self.dt_ms = float(self.cfg["loop"]["dt_ms"])
        self.engine = LIFEngine(pack, seed=identity.seed, gain=make_gain(pack, identity.sex, self.cfg, identity.seed),
                                eps_mv=float(self.cfg["brain"]["eps_mv"]), chunk_steps=int(round(self.dt_ms / 0.1)))
        self.encoder = SensoryEncoder(pack, self.cfg, hunger_gain=identity.hunger_gain)
        self.decoder = MotorDecoder(pack, self.cfg, identity.sex, enabled_reflexes)
        self.ignited = False
        self.last_window_spikes = 0
        self.t_ms = 0.0

    def step(self, state: SensoryState) -> MotorState:
        idx, rate = self.encoder.encode(state)
        self.engine.set_poisson(idx, rate)
        before = int(self.engine.counts.sum())
        self.engine.run(self.dt_ms, record=False)
        self.last_window_spikes = int(self.engine.counts.sum()) - before
        thr = float(self.cfg["loop"]["ignition_spikes_per_100ms"]) * self.dt_ms / 100.0
        self.ignited = self.last_window_spikes > thr
        self.t_ms += self.dt_ms
        return self.decoder.decode(self.engine.counts, self.dt_ms)

    @property
    def hud_label(self) -> str:
        base = self.pack.meta.get("hud_label", f"cerebro completo ({self.pack.n} neuronios)")
        return f"{self.id.name} [{self.id.sex}] {base}" + (" CONTROLE" if self.id.control else "")
