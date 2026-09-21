"""Benchmark: segundos de parede por segundo biologico, pico de memoria, atividade."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np

from brain.engine import LIFEngine
from brain.pack import ConnectomePack
from brain.types import populations


def rss_mb() -> float:
    import psutil
    return psutil.Process(os.getpid()).memory_info().rss / 2**20


def bench(pack: ConnectomePack, stim_idx, rate_hz: float, t_run_ms: float, log=print) -> dict:
    eng = LIFEngine(pack, seed=0)
    eng.set_poisson(stim_idx, rate_hz)
    eng.run(1.0)  # aquece o JIT
    eng.reset(); eng.set_poisson(stim_idx, rate_hz)
    m0 = rss_mb()
    t0 = time.perf_counter()
    rec = eng.run(t_run_ms)
    wall = time.perf_counter() - t0
    m1 = rss_mb()
    res = {
        "pack": pack.name, "n": pack.n, "edges": pack.n_edges, "stim_n": int(len(stim_idx)), "rate_hz": rate_hz,
        "t_run_ms": t_run_ms, "wall_s": wall, "wall_per_bio_s": wall / (t_run_ms / 1000.0),
        "spikes": int(len(rec.idx)), "spikes_per_bio_s": len(rec.idx) / (t_run_ms / 1000.0),
        "neurons_spiking": int(len(np.unique(rec.idx))), "active_at_end": eng.n_active,
        "rss_mb_before": m0, "rss_mb_after": m1,
    }
    log(f"[{pack.name}] {wall:.1f} s de parede por {t_run_ms/1000:.1f} s bio -> {res['wall_per_bio_s']:.1f}x tempo real; "
        f"{res['spikes']} spikes, {res['neurons_spiking']} neuronios ativos, RSS {m1:.0f} MB")
    return res


def main(args) -> int:
    pack = ConnectomePack.load(args.pack)
    pops = populations(pack)
    stim = pops["sugar_R"] if args.stim == "LB3" else pack.select([args.stim], None, startswith=True)
    res = bench(pack, stim, args.rate, args.t_run)
    out = Path("docs/F1_validacao"); out.mkdir(parents=True, exist_ok=True)
    (out / f"{pack.name}_bench.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    return 0
