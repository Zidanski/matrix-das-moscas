"""Testa intervencoes contra a ignicao (laco AL/MB) nos dois sexos.

Para cada intervencao: fracao de trials que ignitam com ORN_DM1 D a `orn_hz`
e com acucar D no max do config, e a taxa de MN9 com acucar (reflexo que nao
queremos perder). Saida: docs/F2_screen/<pack>_interventions.json.
"""

from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

import numpy as np

from brain.pack import ConnectomePack
from interface.config import load_config
from interface.fly_brain import FlyBrain, FlyIdentity

INTERVENTIONS = {
    "nenhuma": {},
    "dopamina_0": {"presyn_gain": {"nt": {"dopamine": 0.0}}},
    "monoaminas_0": {"presyn_gain": {"nt": {"dopamine": 0.0, "octopamine": 0.0, "serotonin": 0.0}}},
    "kc_0.25": {"kc_gain": 0.25},
    "dopamina_0+kc_0.25": {"presyn_gain": {"nt": {"dopamine": 0.0}}, "kc_gain": 0.25},
    "global_0.7": {"global_gain": 0.7},
    "dopamina_0+global_0.85": {"presyn_gain": {"nt": {"dopamine": 0.0}}, "global_gain": 0.85},
}


def apply(cfg, sex, spec):
    c = copy.deepcopy(cfg)
    if "presyn_gain" in spec:
        c["brain"]["presyn_gain"][sex] = spec["presyn_gain"]
    if "kc_gain" in spec:
        c["brain"]["kc_gain"][sex] = spec["kc_gain"]
    if "global_gain" in spec:
        c["brain"]["global_gain"][sex] = spec["global_gain"]
    return c


def trial(pack, sex, c, state, seed, t_ms=1000.0):
    n = int(t_ms / c["loop"]["dt_ms"])
    fly = FlyBrain(pack, FlyIdentity("iv", sex, "#000", seed), c)
    tot, mn9, gf = 0, [], []
    for k in range(n):
        m = fly.step(state)
        tot += fly.last_window_spikes
        if fly.ignited:
            return True, tot, float("nan")
        if k >= 2 * n // 3:
            mn9.append(max(m.rates_hz["MN9"]["L"], m.rates_hz["MN9"]["R"]))
    return False, tot, float(np.mean(mn9))


def main(pack_name="flywire783", trials=3, orn_hz=40.0):
    cfg = load_config()
    pack = ConnectomePack.load(pack_name)
    sex = pack.meta["sex"]
    out = Path("docs/F2_screen"); out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, spec in INTERVENTIONS.items():
        c = apply(cfg, sex, spec)
        c["sensory"]["orn_dm1"]["max_hz"] = orn_hz
        c["sensory"]["orn_da1"]["max_hz"] = orn_hz
        t0 = time.time()
        r = {"intervention": name}
        for cond, state in [("orn_dm1", {"orn_dm1": (0, 1)}), ("orn_da1", {"orn_da1": (0, 1)}), ("sugar", {"sugar": (0, 1)})]:
            ign, spk, mn9 = zip(*[trial(pack, sex, c, state, s) for s in range(trials)])
            r[f"{cond}_ign"] = int(sum(ign)); r[f"{cond}_spikes"] = float(np.mean(spk))
            if cond == "sugar":
                r["sugar_MN9_hz"] = float(np.nanmean(mn9)) if not all(np.isnan(mn9)) else float("nan")
        r["wall_s"] = time.time() - t0
        rows.append(r)
        print(f"[{pack_name}] {name:22s} ign DM1 {r['orn_dm1_ign']}/{trials}  DA1 {r['orn_da1_ign']}/{trials}  acucar {r['sugar_ign']}/{trials}  MN9={r['sugar_MN9_hz']:.1f} Hz  ({r['wall_s']:.0f} s)", flush=True)
        (out / f"{pack_name}_interventions.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "flywire783", int(sys.argv[2]) if len(sys.argv) > 2 else 3))
