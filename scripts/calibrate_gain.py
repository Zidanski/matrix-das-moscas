"""Calibra o ganho global (e opcionalmente o das celulas de Kenyon) por sexo.

Mede, para cada ganho: fracao de trials com ignicao, atividade de fundo e a
resposta acucar -> MN9 (protocolo do mundo: populacao de acucar do lado D no
max_hz do config). Escolhe o maior ganho sem ignicao que ainda preserva
MN9 > 0. O valor escolhido vai para config.yaml (brain.global_gain) e para o
historico de intervencoes. Tudo isso e PREMISSA.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from brain.pack import ConnectomePack
from interface.config import load_config
from interface.fly_brain import FlyBrain, FlyIdentity


def run(pack, sex, cfg, gain, kc_gain, trials, t_ms=1000.0):
    import copy
    cfg = copy.deepcopy(cfg)
    cfg["brain"]["global_gain"][sex] = gain
    cfg["brain"]["kc_gain"][sex] = kc_gain
    n = int(t_ms / cfg["loop"]["dt_ms"])
    ign, mn9, spikes = 0, [], []
    for tr in range(trials):
        fly = FlyBrain(pack, FlyIdentity("cal", sex, "#000", seed=tr), cfg)
        tot, last = 0, []
        for k in range(n):
            m = fly.step({"sugar": (0.0, 1.0)})
            tot += fly.last_window_spikes
            if fly.ignited:
                ign += 1
                break
            if k >= 2 * n // 3:
                last.append(m.rates_hz["MN9"]["all"])
        spikes.append(tot)
        if last:
            mn9.append(float(np.mean(last)))
    return {"gain": gain, "kc_gain": kc_gain, "ignited": ign, "trials": trials,
            "MN9_hz": float(np.mean(mn9)) if mn9 else float("nan"), "spikes_per_s": float(np.mean(spikes))}


def main(pack_name="malecns10", trials=4):
    cfg = load_config()
    pack = ConnectomePack.load(pack_name)
    sex = pack.meta["sex"]
    out = Path("docs/F2_screen"); out.mkdir(parents=True, exist_ok=True)
    rows = []
    grid = [(g, 1.0) for g in (1.0, 0.85, 0.7, 0.55, 0.4)] + [(1.0, 0.25), (0.85, 0.25), (0.7, 0.25)]
    for g, kcg in grid:
        t0 = time.time()
        r = run(pack, sex, cfg, g, kcg, trials)
        r["wall_s"] = time.time() - t0
        rows.append(r)
        print(f"[{pack_name}] gain={g:.2f} kc={kcg:.2f}: ign {r['ignited']}/{trials} MN9={r['MN9_hz']:.1f} Hz spikes/s={r['spikes_per_s']:.0f} ({r['wall_s']:.0f} s)", flush=True)
        (out / f"{pack_name}_gain_calibration.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "malecns10", int(sys.argv[2]) if len(sys.argv) > 2 else 4))
