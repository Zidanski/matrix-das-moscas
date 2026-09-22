"""Relatorio dos dias simulados: metricas por dia, medias, controle vs normal, segredos.

uv run matrix report --runs runs/cem --out docs/F5_relatorio
Le manifest.json de cada dia; escreve CSV, markdown e um grafico PNG.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


def collect(root: Path) -> pd.DataFrame:
    rows = []
    for d in sorted(root.glob("day_*")):
        mf = d / "manifest.json"
        if not mf.exists():
            continue
        m = json.loads(mf.read_text(encoding="utf-8"))
        met = m.get("metrics", {})
        ev = json.loads((d / "events.json").read_text(encoding="utf-8")) if (d / "events.json").exists() else []
        kinds = Counter(e["kind"] for e in ev)
        songs = sum(1 for e in ev if e["kind"] == "estado" and e.get("para") == "cantando")
        control = [f["name"] for f in m["flies"] if f.get("control")]
        sec = met.get("_dia", {}).get("segredos", {})
        # tudo normalizado para 60 s biologicos (dias podem ter 30 ou 60 s)
        k = 60.0 / float(m["seconds"])
        row = {"day": m.get("day_index"), "dir": str(d), "seconds": m["seconds"], "wall_s": round(m.get("wall_s", 0)),
               "control": control[0] if control else "", "brain_mode": m.get("brain_mode")}
        for f in m["flies"]:
            mm = met.get(f["name"], {})
            row[f"dist_{f['name']}"] = mm.get("distancia_cm", 0) * k
            row[f"eat_{f['name']}"] = mm.get("tempo_comendo_s", 0) * k
            row[f"near_{f['name']}"] = mm.get("tempo_perto_de_outra_s", 0) * k
            row[f"ign_{f['name']}"] = mm.get("ticks_convulsao", 0) * k
            row[f"lab_{f['name']}"] = mm.get("tempo_no_subsolo_s", 0) * k
            row[f"cap_{f['name']}"] = mm.get("capturas", 0)
        dia = met.get("_dia", {})
        row.update({"encontros": kinds.get("encontro", 0) * k, "encontros_mf_s": dia.get("encontros_macho_femea_s", 0) * k,
                    "pares_mf": dia.get("pares_mf_que_se_encontraram", 0) * k, "cantos": songs * k, "saltos": kinds.get("salto", 0) * k,
                    "capturas": kinds.get("captura", 0) * k, "entradas_lab": (kinds.get("entrou_no_lab", 0) + kinds.get("afundou", 0)) * k,
                    "esferas": dia.get("esferas_empurradas", 0) * k, "presa_agua": kinds.get("presa_na_agua", 0) * k,
                    "convulsao_ticks": sum(met.get(f["name"], {}).get("ticks_convulsao", 0) for f in m["flies"]) * k,
                    "fugiram": len(dia.get("fugiram", []))})
        for k in ("S1", "S2", "S3", "S4"):
            row[f"{k}_quase"] = sec.get(k, {}).get("quase", 0)
            row[f"{k}_disparou"] = sec.get(k, {}).get("disparou", 0)
        # indice de agregacao medio (fracao do tempo a < 1 cm de outra)
        row["agregacao"] = float(np.mean([met.get(f["name"], {}).get("indice_agregacao", 0) for f in m["flies"]]))
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> str:
    if df.empty:
        return "Nenhum dia encontrado."
    flies = sorted({c[5:] for c in df.columns if c.startswith("dist_")})
    L = [f"# Relatório de {len(df)} dias simulados", ""]
    secs = df.seconds.value_counts().to_dict()
    L.append(f"Dias {int(df.day.min())}–{int(df.day.max())}: " + ", ".join(f"{n} dias de {int(s)} s biológicos" for s, n in sorted(secs.items())) +
             f"; cérebro `{df.brain_mode.iloc[0]}`; {df.wall_s.sum()/3600:.1f} h de parede no total. "
             "Todas as contagens abaixo estão normalizadas para 60 s biológicos por dia.")
    L.append("")
    L.append("## Por dia (médias ± desvio, por 60 s biológicos)")
    L.append("")
    L.append("| Métrica | Normal | Controle (Fil embaralhado) |")
    L.append("|---|---|---|")
    n = df[df.control == ""]; c = df[df.control != ""]

    def cell(s):
        return f"{s.mean():.2f} ± {s.std():.2f} (n={len(s)})" if len(s) else "—"
    for col, lab in [("encontros", "encontros (< 1 cm)"), ("encontros_mf_s", "tempo macho-fêmea a < 1 cm (s)"), ("pares_mf", "pares macho-fêmea"),
                     ("cantos", "cortes iniciadas (canção)"), ("saltos", "fugas (saltos)"), ("capturas", "capturas por robôs"),
                     ("entradas_lab", "entradas no laboratório"), ("esferas", "esferas empurradas"), ("presa_agua", "presas no lago"),
                     ("convulsao_ticks", "janelas em convulsão"), ("agregacao", "índice de agregação"), ("fugiram", "moscas que fugiram")]:
        L.append(f"| {lab} | {cell(n[col])} | {cell(c[col])} |")
    L.append("")
    L.append("## Por mosca (média por dia)")
    L.append("")
    L.append("| Mosca | distância (cm) normal | distância controle | comendo (s) normal | comendo controle | no lab (s) | capturas | convulsão (janelas) |")
    L.append("|---|---|---|---|---|---|---|---|")
    for f in flies:
        L.append(f"| {f} | {n[f'dist_{f}'].mean():.1f} | {c[f'dist_{f}'].mean() if len(c) else float('nan'):.1f} | {n[f'eat_{f}'].mean():.1f} | "
                 f"{c[f'eat_{f}'].mean() if len(c) else float('nan'):.1f} | {df[f'lab_{f}'].mean():.1f} | {df[f'cap_{f}'].sum():.0f} | {df[f'ign_{f}'].sum():.0f} |")
    L.append("")
    L.append("## Segredos")
    L.append("")
    L.append("| Segredo | quase (total) | disparou (total) | dias em que disparou |")
    L.append("|---|---|---|---|")
    for k in ("S1", "S2", "S3", "S4"):
        days = df.loc[df[f"{k}_disparou"] > 0, "day"].astype(int).tolist()
        L.append(f"| {k} | {int(df[f'{k}_quase'].sum())} | {int(df[f'{k}_disparou'].sum())} | {days if days else '—'} |")
    L.append("")
    if df["fugiram"].sum() == 0:
        L.append("Nenhuma mosca escapou. Isso é o experimento, não um defeito.")
    return "\n".join(L) + "\n"


def plot(df: pd.DataFrame, out: Path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return
    flies = sorted({c[5:] for c in df.columns if c.startswith("dist_")})
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    ax = axes[0, 0]
    for f in flies:
        ax.plot(df.day, df[f"dist_{f}"], marker=".", lw=0.8, label=f)
    ax.set_title("distância por dia (cm)"); ax.legend(fontsize=7, ncol=3)
    ax = axes[0, 1]
    ax.plot(df.day, df.encontros, marker=".", label="encontros"); ax.plot(df.day, df.cantos, marker=".", label="cantos"); ax.plot(df.day, df.saltos / 10, marker=".", label="saltos/10")
    ax.set_title("social e sustos"); ax.legend(fontsize=8)
    ax = axes[1, 0]
    for f in flies:
        ax.plot(df.day, df[f"eat_{f}"], marker=".", lw=0.8, label=f)
    ax.set_title("tempo comendo (s)")
    ax = axes[1, 1]
    for k, col in zip(("S1", "S2", "S3", "S4"), ("#ffd166", "#ff8fab", "#7ee787", "#8ecae6")):
        ax.bar(df.day + {"S1": -0.3, "S2": -0.1, "S3": 0.1, "S4": 0.3}[k], df[f"{k}_quase"], width=0.2, color=col, label=f"{k} quase")
    ax.set_title("segredos: quase por dia"); ax.legend(fontsize=7)
    for a in axes.ravel():
        a.grid(alpha=0.2)
        if (df.control != "").any():
            d0 = df.loc[df.control != "", "day"].min()
            a.axvline(d0 - 0.5, color="k", ls="--", lw=0.8)
    fig.suptitle("A Matrix das Moscas — dias simulados (linha tracejada: início do modo controle)")
    fig.tight_layout()
    fig.savefig(out / "dias.png", dpi=120)


def main(args) -> int:
    root = Path(args.runs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df = collect(root)
    df.to_csv(out / "dias.csv", index=False)
    txt = summarize(df)
    (out / "relatorio.md").write_text(txt, encoding="utf-8")
    plot(df, out)
    print(txt)
    return 0
