"""CLI: uv run matrix <comando>."""

from __future__ import annotations

import argparse
import sys
import time


def cmd_build_pack(args: argparse.Namespace) -> int:
    from brain import build_packs
    t0 = time.time()
    if args.connectome == "flywire":
        pack = build_packs.build_flywire(name=args.name or f"flywire{args.version}", min_syn=args.min_syn, version=args.version)
    else:
        pack = build_packs.build_malecns(name=args.name or "malecns10", min_syn=args.min_syn,
                                         brain_only=args.brain_only)
    d = pack.save()
    print(f"[ok] {pack.name}: {pack.n} neuronios, {pack.n_edges} arestas -> {d} ({time.time()-t0:.0f} s)")
    return 0


def cmd_reduce(args: argparse.Namespace) -> int:
    import numpy as np
    from brain.pack import ConnectomePack
    from brain.reduce import reduce_pack
    from brain.types import populations, INPUTS, OUTPUTS
    t0 = time.time()
    pack = ConnectomePack.load(args.pack)
    pops = populations(pack)
    inputs = np.unique(np.concatenate([pops[k] for k in INPUTS if k in pops and len(pops[k])]))
    outputs = np.unique(np.concatenate([pops[k] for k in OUTPUTS if k in pops and len(pops[k])]))
    sub = reduce_pack(pack, inputs, outputs, args.k, name=args.name, min_syn=args.min_syn)
    d = sub.save()
    print(f"[ok] {sub.name}: {sub.n} neuronios ({100*sub.n/pack.n:.1f}%), {sub.n_edges} arestas "
          f"({100*sub.n_edges/pack.n_edges:.1f}%), entradas {len(inputs)}, saidas {len(outputs)} -> {d} ({time.time()-t0:.0f} s)")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from scripts import validate
    return validate.main(args)


def cmd_screen(args: argparse.Namespace) -> int:
    from scripts import screen
    return screen.main(args.pack, args.trials, args.t_pre, args.t_stim)


def cmd_calibrate_gain(args: argparse.Namespace) -> int:
    from scripts import calibrate_gain
    return calibrate_gain.main(args.pack, args.trials)


def cmd_simulate(args: argparse.Namespace) -> int:
    from scripts import simulate_days
    return simulate_days.main(args)


def cmd_bench(args: argparse.Namespace) -> int:
    from scripts import benchmark
    return benchmark.main(args)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="matrix", description="A Matrix das Moscas")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build-pack", help="converte dados brutos em CSR")
    b.add_argument("connectome", choices=["flywire", "malecns"])
    b.add_argument("--name")
    b.add_argument("--min-syn", type=int, default=1, help="limiar de sinapses por aresta (1 = tudo)")
    b.add_argument("--brain-only", action="store_true", help="MaleCNS: descarta VNC")
    b.add_argument("--version", type=int, default=783, choices=[630, 783], help="FlyWire: materializacao (630 = a do artigo de Shiu)")
    b.set_defaults(func=cmd_build_pack)

    r = sub.add_parser("reduce", help="subcircuito de k saltos entre entradas e saidas")
    r.add_argument("--pack", default="flywire783")
    r.add_argument("--k", type=int, default=4)
    r.add_argument("--name")
    r.add_argument("--min-syn", type=int, default=1)
    r.set_defaults(func=cmd_reduce)

    v = sub.add_parser("validate", help="acucar/amargo -> MN9 e comparacao com Brian2")
    v.add_argument("--pack", default="flywire783")
    v.add_argument("--trials", type=int, default=5)
    v.add_argument("--t-run", type=float, default=1000.0, help="ms por trial")
    v.add_argument("--rates", default="10,25,50,100,150,200")
    v.add_argument("--brian2", action="store_true", help="tambem roda Brian2 (lento)")
    v.add_argument("--out", default="docs/F1_validacao")
    v.set_defaults(func=cmd_validate)

    bm = sub.add_parser("bench", help="benchmark de velocidade e memoria")
    bm.add_argument("--pack", default="flywire783")
    bm.add_argument("--t-run", type=float, default=1000.0)
    bm.add_argument("--rate", type=float, default=100.0)
    bm.add_argument("--stim", default="LB3", help="rotulo de tipo estimulado (prefixo)")
    bm.set_defaults(func=cmd_bench)

    sc = sub.add_parser("screen", help="SCREEN: cada entrada unilateral x cada saida, por sexo")
    sc.add_argument("--pack", default="flywire783")
    sc.add_argument("--trials", type=int, default=2)
    sc.add_argument("--t-pre", type=float, default=150.0)
    sc.add_argument("--t-stim", type=float, default=600.0)
    sc.set_defaults(func=cmd_screen)

    cg = sub.add_parser("calibrate-gain", help="ganho global/KC por sexo vs ignicao e acucar->MN9")
    cg.add_argument("--pack", default="malecns10")
    cg.add_argument("--trials", type=int, default=4)
    cg.set_defaults(func=cmd_calibrate_gain)

    sm = sub.add_parser("simulate", help="simula dias do mundo e grava replays em runs/")
    sm.add_argument("--days", type=int, default=1)
    sm.add_argument("--start", type=int, default=0, help="indice do primeiro dia")
    sm.add_argument("--seconds", type=float, default=30.0, help="segundos biologicos por dia")
    sm.add_argument("--brain", choices=["reduced", "full"], default="reduced")
    sm.add_argument("--control", default=None, help="nome da mosca com conectoma embaralhado (ex.: Fil)")
    sm.add_argument("--out", default="runs")
    sm.set_defaults(func=cmd_simulate)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
