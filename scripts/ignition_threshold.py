"""Limiar de ignicao por entrada: maior taxa (Hz/neuronio) que NAO acende o laco.

Para cada populacao de entrada (lado D, populacao inteira), roda 1 s com taxas
crescentes e registra a primeira que ignita (>10 000 disparos/100 ms). O
config.yaml deve ficar abaixo (margem de 30 %). Saida:
docs/F2_screen/<pack>_ignition.json e .csv.
"""

from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

import pandas as pd

from brain.pack import ConnectomePack
from brain.types import INPUTS
from interface.config import load_config
from interface.fly_brain import FlyBrain, FlyIdentity

RATES = [10, 20, 30, 40, 60, 80]


def ignites(pack, sex, cfg, name, rate, trials=2, t_ms=1000.0):
    c = copy.deepcopy(cfg)
    c["sensory"][name]["max_hz"] = rate
    c["sensory"][name]["gamma"] = 1.0
    n = int(t_ms / c["loop"]["dt_ms"])
    for tr in range(trials):
        fly = FlyBrain(pack, FlyIdentity("ign", sex, "#000", seed=tr), c)
        for _ in range(n):
            fly.step({name: (0.0, 1.0)})
            if fly.ignited:
                return True
    return False


def main(pack_name="flywire783", trials=2, monoamines_zero=False, tag=""):
    cfg = load_config()
    pack_sex = ConnectomePack.load(pack_name).meta["sex"]
    if monoamines_zero:
        cfg["brain"]["presyn_gain"][pack_sex] = {"nt": {"dopamine": 0.0, "octopamine": 0.0, "serotonin": 0.0}}
    pack = ConnectomePack.load(pack_name)
    sex = pack.meta["sex"]
    out = Path("docs/F2_screen"); out.mkdir(parents=True, exist_ok=True)
    probe = FlyBrain(pack, FlyIdentity("p", sex, "#000", 0), cfg)
    rows = []
    for name in [n for n in INPUTS if n in probe.encoder.pops]:
        t0 = time.time()
        first = None
        for r in RATES:
            if ignites(pack, sex, cfg, name, r, trials):
                first = r
                break
        n_pop = len(probe.encoder.pops[name]["R"])
        rows.append({"input": name, "n_R": n_pop, "first_igniting_hz": first, "max_stable_hz": (RATES[RATES.index(first) - 1] if first and RATES.index(first) > 0 else (0 if first else RATES[-1])),
                     "config_max_hz": (cfg["sensory"][name]["max_hz"][sex] if isinstance(cfg["sensory"][name]["max_hz"], dict) else cfg["sensory"][name]["max_hz"]), "wall_s": time.time() - t0})
        print(f"[{pack_name}] {name:9s} n_D={n_pop:4d} primeira ignicao={first} Hz  estavel ate={rows[-1]['max_stable_hz']} Hz  config={rows[-1]['config_max_hz']} ({rows[-1]['wall_s']:.0f} s)", flush=True)
        pd.DataFrame(rows).to_csv(out / f"{pack_name}_ignition{tag}.csv", index=False)
    (out / f"{pack_name}_ignition{tag}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    mz = len(sys.argv) > 3 and sys.argv[3] == "monoamines0"
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "flywire783", int(sys.argv[2]) if len(sys.argv) > 2 else 2,
                  monoamines_zero=mz, tag="_monoamines0" if mz else ""))
