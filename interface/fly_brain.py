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


def make_pre_gain(pack: ConnectomePack, sex: str, cfg: dict) -> np.ndarray:
    """Ganho por neuronio PRE-sinaptico: por neurotransmissor (ex.: dopamina 0 =
    neuromoduladores sem efeito excitatorio rapido) e por rotulo de tipo."""
    pre = np.ones(pack.n, dtype=np.float64)
    spec = cfg["brain"].get("presyn_gain", {}).get(sex, {}) or {}
    nt = pack.neurons["nt"].astype("string").fillna("").str.lower().to_numpy().astype(str) if "nt" in pack.neurons else np.full(pack.n, "", dtype=str)
    for name, g in (spec.get("nt", {}) or {}).items():
        pre[nt == name.lower()] *= float(g)
    for label, g in (spec.get("type_prefix", {}) or {}).items():
        pre[pack.select([label], None, startswith=True)] *= float(g)
    # correcao de sinal por classe/tipo (ex.: ALLN inibitorio): inverte o sinal das
    # saidas dos neuronios cujo sinal previsto difere do desejado
    rules = cfg["brain"].get("sign_override", {}).get(sex, []) or []
    if rules:
        cur = current_sign(pack)
        for rule in rules:
            want = int(rule["sign"])
            if "cell_class" in rule:
                m = (pack.neurons["cell_class"].astype("string").fillna("") == rule["cell_class"]).to_numpy()
            else:
                m = np.zeros(pack.n, dtype=bool)
                m[pack.select([rule["type_prefix"]], None, startswith=True)] = True
            flip = m & (cur != 0) & (cur != want)
            pre[flip] *= -1.0
    return pre


def current_sign(pack: ConnectomePack) -> np.ndarray:
    """Sinal efetivo de cada neuronio nas arestas do pacote (0 = sem saidas)."""
    ip = np.asarray(pack.indptr)
    w = np.asarray(pack.weights)
    has = ip[1:] > ip[:-1]
    first = np.where(has, ip[:-1], 0)
    s = np.sign(w[first]).astype(np.int8)
    s[~has] = 0
    return s


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
                                eps_mv=float(self.cfg["brain"]["eps_mv"]), chunk_steps=int(round(self.dt_ms / 0.1)),
                                pre_gain=make_pre_gain(pack, identity.sex, self.cfg))
        self.encoder = SensoryEncoder(pack, self.cfg, hunger_gain=identity.hunger_gain)
        if enabled_reflexes is None:
            enabled_reflexes = set(self.cfg.get("reflexes_enabled", {}).get(identity.sex, []) or self.cfg["motor"].keys())
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
