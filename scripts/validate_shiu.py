"""Reproducao exata do experimento de Shiu et al. 2024 com o nosso motor.

Mesmos neuronios (listas oficiais, v630), mesmo protocolo (Poisson a r Hz,
1 s, 30 trials), leitura de MN9 E/D. Compara com os arquivos de resultado
publicados no repositorio (Brian2). Tambem roda no v783 com os IDs que
sobreviveram a materializacao.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from brain.engine import LIFEngine
from brain.pack import ConnectomePack
from brain import shiu_lists as SL
from scripts.validate import exploded


def ids_to_idx(pack: ConnectomePack, ids):
    id2idx = pd.Series(pack.neurons["idx"].to_numpy(), index=pack.neurons["id"].to_numpy())
    found = [i for i in ids if i in id2idx.index]
    return id2idx.loc[found].to_numpy().astype(np.int32), len(found), len(ids)


def run(pack, stim, rate, trials, mn9_l, mn9_r, t_run=1000.0):
    rows = []
    for tr in range(trials):
        eng = LIFEngine(pack, seed=tr)
        eng.set_poisson(stim, rate)
        rec = eng.run(t_run)
        rows.append({"trial": tr, "spikes": int(len(rec.idx)), "exploded": exploded(rec, t_run),
                     "MN9_L": float((rec.idx == mn9_l).sum()) if mn9_l is not None else np.nan,
                     "MN9_R": float((rec.idx == mn9_r).sum()) if mn9_r is not None else np.nan})
    return pd.DataFrame(rows)


def published_reference():
    out = {}
    for name in ["sugarR_100Hz", "sugarR"]:
        p = Path("data/raw/shiu") / f"{name}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        nt = d.trial.nunique()
        out[name] = {"trials": int(nt),
                     "MN9_L_hz": float((d.flywire_id == SL.MN9_L_630).sum() / nt),
                     "MN9_R_hz": float((d.flywire_id == SL.MN9_R_630).sum() / nt),
                     "spikes_per_trial": d.groupby("trial").size().describe()[["min", "50%", "max"]].to_dict()}
    return out


def main(trials: int = 30) -> int:
    out = Path("docs/F1_validacao")
    out.mkdir(parents=True, exist_ok=True)
    result = {"published_brian2": published_reference(), "ours": {}}
    print("publicado (Brian2, Shiu):", json.dumps(result["published_brian2"], indent=1))
    for pack_name in ["flywire630", "flywire783"]:
        if not (Path("data/packs") / pack_name / "meta.json").exists():
            print("pacote ausente:", pack_name)
            continue
        pack = ConnectomePack.load(pack_name)
        sugar, ns, nt = ids_to_idx(pack, SL.SUGAR_R_630)
        bitter, nb, ntb = ids_to_idx(pack, SL.BITTER_R_630)
        l, _, _ = ids_to_idx(pack, [SL.MN9_L_630])
        r, _, _ = ids_to_idx(pack, [SL.MN9_R_630])
        mn9_l = int(l[0]) if len(l) else None
        mn9_r = int(r[0]) if len(r) else None
        print(f"[{pack_name}] acucar D {ns}/{nt} ids encontrados, amargo D {nb}/{ntb}, MN9 L {'ok' if mn9_l is not None else 'AUSENTE'}, MN9 R {'ok' if mn9_r is not None else 'AUSENTE'}")
        res = {"sugar_ids_found": ns, "sugar_ids_total": nt, "bitter_ids_found": nb}
        for rate in [100.0, 200.0]:
            t0 = time.time()
            df = run(pack, sugar, rate, trials, mn9_l, mn9_r)
            res[f"sugarR_{int(rate)}Hz"] = {
                "MN9_L_hz": float(df.MN9_L.mean()), "MN9_R_hz": float(df.MN9_R.mean()),
                "MN9_L_sd": float(df.MN9_L.std()), "MN9_R_sd": float(df.MN9_R.std()),
                "spikes_per_trial": {"min": int(df.spikes.min()), "50%": float(df.spikes.median()), "max": int(df.spikes.max())},
                "exploded_frac": float(df.exploded.mean()), "trials": trials, "wall_s": time.time() - t0}
            print(f"  {int(rate)} Hz: MN9_L {df.MN9_L.mean():.1f} Hz  MN9_R {df.MN9_R.mean():.1f} Hz  spikes/trial med {df.spikes.median():.0f}  disparados {df.exploded.mean():.0%}  ({time.time()-t0:.0f} s)", flush=True)
        # amargo 100 Hz junto com acucar 100 Hz (Fig. 3a)
        both = np.concatenate([sugar, bitter])
        rows = []
        for tr in range(trials):
            eng = LIFEngine(pack, seed=100 + tr)
            eng.set_poisson(both, np.concatenate([np.full(len(sugar), 100.0), np.full(len(bitter), 100.0)]))
            rec = eng.run(1000.0)
            rows.append({"MN9_L": float((rec.idx == mn9_l).sum()) if mn9_l is not None else np.nan,
                         "MN9_R": float((rec.idx == mn9_r).sum()) if mn9_r is not None else np.nan,
                         "exploded": exploded(rec, 1000.0)})
        db = pd.DataFrame(rows)
        res["sugar100_bitter100"] = {"MN9_L_hz": float(db.MN9_L.mean()), "MN9_R_hz": float(db.MN9_R.mean()),
                                     "exploded_frac": float(db.exploded.mean())}
        print(f"  acucar 100 + amargo 100: MN9_L {db.MN9_L.mean():.1f} Hz  MN9_R {db.MN9_R.mean():.1f} Hz  disparados {db.exploded.mean():.0%}", flush=True)
        result["ours"][pack_name] = res
    (out / "shiu_protocol.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("salvo em", out / "shiu_protocol.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 30))
