"""Portao da F1: acucar -> MN9 sobe; amargo reduz; nos dois conectomas.

Reproduz o experimento central de Shiu et al. 2024: GRNs de acucar de UM lado
(direito) estimulados com Poisson a varias taxas, leitura da taxa de MN9
(esquerdo e direito). Depois acucar 100 Hz + amargo (mesmo lado) 0..200 Hz.
Opcionalmente roda o mesmo experimento no Brian2 (alvo numpy, lento) para
comparar as taxas medias.

Rotulos (nunca IDs no codigo):
  FlyWire : acucar = cell_type LB3 (cell_sub_class 'sugar/water'), amargo =
            cell_sub_class 'bitter', MN9 = cell_type CB0701
  MaleCNS : acucar = type LB3b + LB3c, amargo = flywire_type em {LB1a,LB1d,LB1b,LB1c,LB1e},
            MN9 = type MN9
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from brain.engine import LIFEngine
from brain.pack import ConnectomePack
from brain.params import SHIU
from brain.types import populations


EXPLOSION_SPIKES_PER_100MS = 10000  # laco recorrente auto-sustentado (ver docs/F1_validacao.md)


def exploded(rec, t_run_ms) -> bool:
    """Trial 'disparado': ultimos 100 ms com mais de 10 mil disparos (atividade auto-sustentada)."""
    last = rec.step >= int((t_run_ms - 100.0) / 0.1)
    return bool(last.sum() > EXPLOSION_SPIKES_PER_100MS)


def rate_of(rec, idx, t_run_ms):
    if len(idx) == 0:
        return float("nan")
    m = np.isin(rec.idx, idx)
    return m.sum() / (t_run_ms / 1000.0) / len(idx)


def run_sweep(pack, stim_idx, read, rates, trials, t_run_ms, stim2_idx=None, rate2=0.0, seed0=0, log=print):
    log = (lambda *a, **k: print(*a, **{**k, 'flush': True})) if log is print else log
    rows = []
    for r in rates:
        per_trial = {k: [] for k in read}
        per_trial_ok = {k: [] for k in read}
        n_expl = 0
        t0 = time.time()
        for tr in range(trials):
            eng = LIFEngine(pack, seed=seed0 + tr)
            idx = stim_idx
            rate_vec = np.full(len(stim_idx), float(r))
            if stim2_idx is not None and len(stim2_idx):
                idx = np.concatenate([stim_idx, stim2_idx])
                rate_vec = np.concatenate([rate_vec, np.full(len(stim2_idx), float(rate2))])
            eng.set_poisson(idx, rate_vec)
            rec = eng.run(t_run_ms)
            ex = exploded(rec, t_run_ms)
            n_expl += int(ex)
            for k, v in read.items():
                per_trial[k].append(rate_of(rec, v, t_run_ms))
                if not ex:
                    per_trial_ok[k].append(rate_of(rec, v, t_run_ms))
        row = {"rate_hz": r, "n_spikes_last_trial": int(len(rec.idx)), "wall_s": (time.time() - t0) / trials,
               "exploded_frac": n_expl / trials}
        for k in read:
            row[k + "_hz"] = float(np.mean(per_trial[k]))
            row[k + "_sd"] = float(np.std(per_trial[k]))
            row[k + "_hz_stable"] = float(np.mean(per_trial_ok[k])) if per_trial_ok[k] else float("nan")
        rows.append(row)
        log(f"  rate={r:>5} " + " ".join(f"{k}={row[k+'_hz']:.1f}(estavel {row[k+'_hz_stable']:.1f})" for k in read)
            + f"  disparados {n_expl}/{trials}  ({row['wall_s']:.1f} s/trial)", flush=True)
    return pd.DataFrame(rows)


def main(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pack = ConnectomePack.load(args.pack)
    pops = populations(pack)
    rates = [float(x) for x in args.rates.split(",")]
    sugar_r = pops["sugar_R"]
    bitter_r = pops["bitter_R"]
    read = {"MN9_L": pops["MN9_L"], "MN9_R": pops["MN9_R"]}
    print(f"[{pack.name}] acucar D n={len(sugar_r)} amargo D n={len(bitter_r)} MN9 L/R n={len(read['MN9_L'])}/{len(read['MN9_R'])}")
    print("== varredura de acucar (lado direito)")
    df_sugar = run_sweep(pack, sugar_r, read, rates, args.trials, args.t_run)
    df_sugar.to_csv(out / f"{pack.name}_sugar_sweep.csv", index=False)
    print("== acucar 100 Hz + amargo (lado direito) 0..200 Hz")
    bitter_rates = [0, 50, 100, 200]
    df_bitter = run_sweep(pack, sugar_r, read, [100.0], args.trials, args.t_run) .assign(bitter_hz=0)
    rows = [df_bitter]
    for br in bitter_rates[1:]:
        d = run_sweep(pack, bitter_r, read, [float(br)], args.trials, args.t_run, stim2_idx=sugar_r, rate2=100.0)
        rows.append(d.assign(bitter_hz=br))
    df_bitter = pd.concat(rows, ignore_index=True)
    df_bitter.to_csv(out / f"{pack.name}_bitter_vs_sugar100.csv", index=False)

    result = {
        "pack": pack.name, "trials": args.trials, "t_run_ms": args.t_run,
        "sugar_sweep": df_sugar.to_dict(orient="records"),
        "bitter": df_bitter.to_dict(orient="records"),
    }
    # criterios do portao
    mn9 = np.nan_to_num(df_sugar["MN9_L_hz_stable"].to_numpy() + df_sugar["MN9_R_hz_stable"].to_numpy())
    monotone = bool(np.all(np.diff(mn9) >= -1e-9)) and bool(mn9[-1] > mn9[0])
    b = df_bitter.sort_values("bitter_hz")
    bsum = np.nan_to_num(b["MN9_L_hz_stable"].to_numpy() + b["MN9_R_hz_stable"].to_numpy())
    bitter_reduces = bool(bsum[-1] < 0.5 * bsum[0]) if bsum[0] > 0 else False
    result["gate"] = {"sugar_monotone_increase": monotone, "bitter_halves_mn9": bitter_reduces,
                      "mn9_at_100hz_stable": float(df_sugar.loc[df_sugar.rate_hz == 100.0, ["MN9_L_hz_stable", "MN9_R_hz_stable"]].sum(axis=1).iloc[0]) if (df_sugar.rate_hz == 100.0).any() else None,
                      "exploded_frac_by_rate": dict(zip(df_sugar.rate_hz.astype(float), df_sugar.exploded_frac.astype(float)))}
    print("PORTAO:", result["gate"])

    if args.brian2:
        from brain.brian2_ref import run_brian2
        print("== Brian2 (numpy) acucar 100 Hz, mesmas populacoes, comparacao de taxas")
        pre_all, post_all, w_all = _edges(pack)
        b_rows = []
        for tr in range(args.trials):
            t0 = time.time()
            bi, bs = run_brian2(pack.n, pre_all, post_all, w_all, args.t_run, poisson_idx=sugar_r,
                                poisson_rate_hz=100.0, seed=1000 + tr)
            rec = type("R", (), {"idx": bi, "step": bs})
            b_rows.append({k: rate_of(rec, v, args.t_run) for k, v in read.items()} | {"n_spikes": int(len(bi)), "wall_s": time.time() - t0})
            print(f"  brian2 trial {tr}: {b_rows[-1]}")
        result["brian2_sugar100"] = b_rows
        result["ours_sugar100"] = df_sugar.loc[df_sugar.rate_hz == 100.0].to_dict(orient="records")
    (out / f"{pack.name}_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("salvo em", out)
    return 0


def _edges(pack):
    pre = np.repeat(np.arange(pack.n), np.diff(pack.indptr))
    return pre, np.asarray(pack.indices), np.asarray(pack.weights)
