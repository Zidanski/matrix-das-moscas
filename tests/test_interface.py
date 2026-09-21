"""Testes da interface sensorio-motora com um pacote sintetico (sem dados)."""

import numpy as np
import pandas as pd
import pytest

from brain.pack import ConnectomePack
from interface.config import load_config
from interface.sensory import SensoryEncoder
from interface.motor import MotorDecoder, RateReader
from interface.fly_brain import FlyBrain, FlyIdentity, make_gain


def synthetic_pack(sex="female"):
    """12 neuronios: 0-3 acucar (E,E,D,D), 4-5 MN9 (E,D), 6-7 DNa02 (E,D), 8-9 DNp01, 10-11 KC."""
    n = 12
    types = ["LB3", "LB3", "LB3", "LB3", "CB0701", "CB0701", "DNa02", "DNa02", "DNp01", "DNp01", "KCab", "KCab"]
    if sex == "male":
        types = ["LB3b", "LB3b", "LB3c", "LB3c", "MN9", "MN9", "DNa02", "DNa02", "DNp01", "DNp01", "KCab", "KCab"]
    sides = ["L", "L", "R", "R", "L", "R", "L", "R", "L", "R", "L", "R"]
    neurons = pd.DataFrame({"idx": np.arange(n), "id": np.arange(n), "type": types, "side": sides,
                            "cell_class": ["gustatory"] * 4 + ["motor"] * 2 + ["dn"] * 4 + ["Kenyon_Cell"] * 2,
                            "cell_sub_class": [""] * n, "hemibrain_type": [""] * n, "flywire_type": types})
    # acucar -> MN9 forte (300 sinapses) e acucar D -> DNa02 E (contralateral)
    edges = [(0, 4, 300), (1, 4, 300), (2, 5, 300), (3, 5, 300), (2, 6, 300), (3, 6, 300)]
    pre, post, w = (np.array([e[i] for e in edges]) for i in range(3))
    return ConnectomePack.from_edges("synthetic", n, pre, post, w, neurons, {"sex": sex})


def test_config_loads_and_is_complete():
    cfg = load_config()
    for k in ("loop", "brain", "sensory", "motor", "interventions"):
        assert k in cfg
    assert cfg["loop"]["dt_ms"] == 15.0
    assert all("max_hz" in v for v in cfg["sensory"].values())


def test_encoder_rates_by_side_and_missing():
    cfg = load_config()
    enc = SensoryEncoder(synthetic_pack(), cfg)
    assert "ppk23" in enc.missing            # femea nao tem
    idx, rate = enc.encode({"sugar": (0.0, 1.0)})
    assert sorted(idx.tolist()) == [2, 3] and np.allclose(rate, cfg["sensory"]["sugar"]["max_hz"])
    idx, rate = enc.encode({"sugar": (0.5, 0.0)})
    assert sorted(idx.tolist()) == [0, 1] and np.allclose(rate, 0.5 * cfg["sensory"]["sugar"]["max_hz"])
    enc2 = SensoryEncoder(synthetic_pack(), cfg, hunger_gain=2.0)
    _, r2 = enc2.encode({"sugar": (0.0, 1.0)})
    assert np.allclose(r2, 2 * cfg["sensory"]["sugar"]["max_hz"])


def test_rate_reader_exponential_window():
    p = synthetic_pack()
    rr = RateReader(p, ["MN9"], tau_ms=75.0)
    counts = np.zeros(p.n, dtype=np.int64)
    rr.update(counts, 15.0)
    counts[4] = 3; counts[5] = 3           # 6 disparos em 2 neuronios em 15 ms -> 200 Hz instantaneo
    r = rr.update(counts, 15.0)
    a = np.exp(-15 / 75)
    assert r["MN9"]["all"] == pytest.approx((1 - a) * 200.0)
    assert r["MN9"]["L"] == pytest.approx((1 - a) * 200.0)


def test_fly_brain_sugar_right_feeds_and_turns():
    cfg = load_config()
    fly = FlyBrain(synthetic_pack(), FlyIdentity("t", "female", "#000", seed=0), cfg)
    m = None
    for _ in range(40):
        m = fly.step({"sugar": (0.0, 1.0)})
    assert m.feed is True
    assert m.rates_hz["MN9"]["R"] > m.rates_hz["MN9"]["L"]
    assert m.turn_rad_s > 0            # DNa02 E > D -> vira para a esquerda (convencao do config)
    assert not fly.ignited


def test_gain_jitter_and_kc_gain():
    cfg = load_config()
    cfg["brain"]["kc_gain"]["female"] = 0.25
    g = make_gain(synthetic_pack(), "female", cfg, seed=1)
    assert g.shape == (12,) and 0.8 < g[:10].mean() < 1.2
    assert np.all(g[10:] < 0.4)
    g2 = make_gain(synthetic_pack(), "female", cfg, seed=1)
    assert np.array_equal(g, g2)       # deterministico por semente


def test_decoder_respects_enabled_set():
    cfg = load_config()
    fly = FlyBrain(synthetic_pack(), FlyIdentity("t", "female", "#000", seed=0), cfg, enabled_reflexes={"turn"})
    m = None
    for _ in range(40):
        m = fly.step({"sugar": (0.0, 1.0)})
    assert m.feed is False and m.turn_rad_s > 0
