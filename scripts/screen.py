"""SCREEN: para cada entrada unilateral, por sexo, mede cada saida.

Protocolo por (pacote, entrada, lado): estimulo maximo do config (valor 1.0 no
lado dado, 0 no outro) durante `t_stim` ms apos `t_pre` ms de silencio;
`trials` sementes. Le todas as populacoes de saida (E, D) com a mesma janela
exponencial do mundo, no ultimo terco do estimulo. Registra ignicao.
Tambem roda pares sociais (ex.: cVA + contato, cancao + cVA).

Saida: docs/F2_screen/<pack>_screen.csv (linhas input x lado x output) e um
mapa de calor; docs/F2_screen.md e escrito a mao a partir disso.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from brain.pack import ConnectomePack
from brain.types import INPUTS, OUTPUTS
from interface.config import load_config
from interface.fly_brain import FlyBrain, FlyIdentity

PAIRS = {  # combinacoes sociais (nome -> estado sensorial)
    "cva+ppk23_R": {"orn_da1": (0, 1), "orn_dl3": (0, 1), "ppk23": (0, 1)},
    "cva+song_R": {"orn_da1": (0, 1), "orn_dl3": (0, 1), "jo_a": (0, 1), "jo_b": (0, 1)},
    "cva+lc11_R": {"orn_da1": (0, 1), "orn_dl3": (0, 1), "lc11": (0, 1)},
    "sugar+bitter_R": {"sugar": (0, 1), "bitter": (0, 1)},
    "loom_both": {"lc4": (1, 1), "lplc2": (1, 1)},
}


def run_condition(pack, sex, state, trials, t_pre_ms, t_stim_ms, cfg, seed0=0):
    dt = cfg["loop"]["dt_ms"]
    n_pre, n_stim = int(t_pre_ms / dt), int(t_stim_ms / dt)
    rows, ign = [], 0
    spikes_total = 0
    for tr in range(trials):
        fly = FlyBrain(pack, FlyIdentity("scr", sex, "#000", seed=seed0 + tr), cfg)
        for _ in range(n_pre):
            fly.step({})
        acc = None
        n_read = 0
        for k in range(n_stim):
            m = fly.step(state)
            spikes_total += fly.last_window_spikes
            if fly.ignited:
                ign += 1
                break
            if k >= 2 * n_stim // 3:
                r = {f"{p}_{s}": v for p, d in m.rates_hz.items() for s, v in d.items()}
                acc = r if acc is None else {k2: acc[k2] + r[k2] for k2 in r}
                n_read += 1
        if acc:
            rows.append({k2: v / n_read for k2, v in acc.items()})
    df = pd.DataFrame(rows)
    return (df.mean().to_dict() if len(df) else {}), ign, spikes_total / max(1, trials)


def main(pack_name: str, trials: int = 2, t_pre_ms: float = 150.0, t_stim_ms: float = 600.0, out_dir="docs/F2_screen") -> int:
    cfg = load_config()
    pack = ConnectomePack.load(pack_name)
    sex = pack.meta["sex"]
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    probe = FlyBrain(pack, FlyIdentity("probe", sex, "#000", 0), cfg)
    inputs = [n for n in INPUTS if n in probe.encoder.pops]
    outputs = [n for n in OUTPUTS if n in probe.decoder.reader.groups]
    print(f"[{pack_name}] sexo={sex} entradas={inputs} ausentes={probe.encoder.missing}", flush=True)
    print(f"  saidas={outputs}", flush=True)
    conds = [("baseline", {})] + [(f"{n}_{side}", {n: (1.0, 0.0) if side == "L" else (0.0, 1.0)}) for n in inputs for side in ("L", "R")]
    conds += [(k, v) for k, v in PAIRS.items() if all(n in probe.encoder.pops for n in v)]
    records = []
    for name, state in conds:
        t0 = time.time()
        rates, ign, spk = run_condition(pack, sex, state, trials, t_pre_ms, t_stim_ms, cfg)
        rec = {"condition": name, "ignited": ign, "trials": trials, "spikes_per_trial": spk, "wall_s": time.time() - t0}
        rec.update(rates)
        records.append(rec)
        top = sorted(((k, v) for k, v in rates.items() if k.endswith("_all") and v > 0.5), key=lambda kv: -kv[1])[:6]
        print(f"  {name:18s} ign={ign}/{trials} spk={spk:8.0f} " + " ".join(f"{k[:-4]}={v:.0f}" for k, v in top) + f"  ({time.time()-t0:.0f} s)", flush=True)
        pd.DataFrame(records).to_csv(out / f"{pack_name}_screen.csv", index=False)
    df = pd.DataFrame(records)
    # matriz input x output (taxa total) + mapa de calor
    cols = [f"{o}_all" for o in outputs if f"{o}_all" in df]
    mat = df.set_index("condition")[cols].fillna(0.0)
    mat.columns = [c[:-4] for c in cols]
    mat.to_csv(out / f"{pack_name}_matrix.csv")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(1.2 + 0.45 * len(mat.columns), 1.5 + 0.28 * len(mat)))
        im = ax.imshow(np.log10(mat.to_numpy() + 1), cmap="magma", aspect="auto")
        ax.set_xticks(range(len(mat.columns))); ax.set_xticklabels(mat.columns, rotation=90, fontsize=7)
        ax.set_yticks(range(len(mat))); ax.set_yticklabels(mat.index, fontsize=7)
        ax.set_title(f"SCREEN {pack_name} ({sex}): log10(Hz+1) das saidas por entrada unilateral", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.03)
        fig.tight_layout(); fig.savefig(out / f"{pack_name}_screen.png", dpi=130)
    except Exception as e:  # noqa: BLE001
        print("sem figura:", e)
    (out / f"{pack_name}_meta.json").write_text(json.dumps({"inputs": inputs, "outputs": outputs, "missing_inputs": probe.encoder.missing,
                                                             "trials": trials, "t_pre_ms": t_pre_ms, "t_stim_ms": t_stim_ms}, indent=2), encoding="utf-8")
    print("salvo em", out, flush=True)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "flywire783", int(sys.argv[2]) if len(sys.argv) > 2 else 2))
