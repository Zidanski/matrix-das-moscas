"""Formato de replay de um "dia".

runs/<dia>/
  manifest.json   mundo (config), moscas, campos, dt, ticks, cerebros (rotulo do HUD)
  frames.bin      float32 [ticks, n_moscas, n_campos] little-endian (pose, estado, taxas)
  objects.bin     float32 [ticks, n_esferas, 2] (x, y das esferas)
  events.json     lista de eventos {t, tipo, moscas, dados}
  spikes.npz      opcional: disparos amostrados por mosca (F5)
O visualizador web le manifest.json + frames.bin com DataView.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

STATE_IDS = {"parada": 0, "andando": 1, "re": 2, "comendo": 3, "saltando": 4, "cantando": 5,
             "presa": 6, "convulsao": 7, "capturada": 8, "grooming": 9, "lutando": 10, "cortejando": 11}
STATE_NAMES = {v: k for k, v in STATE_IDS.items()}

BASE_FIELDS = ["x", "y", "z", "heading", "v", "omega", "state", "hunger", "ignited", "spikes", "feed", "jump", "song", "court", "stuck"]


class ReplayWriter:
    def __init__(self, out_dir: Path, manifest: dict, rate_pops: list[str], n_flies: int, n_spheres: int, input_pops: list[str] | None = None):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.rate_pops = rate_pops
        self.input_pops = input_pops or []
        self.fields = BASE_FIELDS + [f"rate_{p}_{s}" for p in rate_pops for s in ("all", "L", "R")] + [f"in_{p}_{s}" for p in self.input_pops for s in ("L", "R")]
        self.manifest = dict(manifest)
        self.manifest.update({"fields": self.fields, "n_flies": n_flies, "n_spheres": n_spheres, "state_ids": STATE_IDS})
        self.frames: list[np.ndarray] = []
        self.objs: list[np.ndarray] = []
        self.events: list[dict] = []

    def add_frame(self, fly_rows: list[list[float]], sphere_xy: list[tuple[float, float]]):
        self.frames.append(np.asarray(fly_rows, dtype=np.float32))
        self.objs.append(np.asarray(sphere_xy, dtype=np.float32).reshape(-1, 2))

    def add_event(self, t: float, kind: str, flies: list[str], **data):
        self.events.append({"t": round(float(t), 3), "kind": kind, "flies": flies, **data})

    def close(self, extra_manifest: dict | None = None):
        fr = np.stack(self.frames) if self.frames else np.zeros((0, self.manifest["n_flies"], len(self.fields)), np.float32)
        ob = np.stack(self.objs) if self.objs else np.zeros((0, self.manifest["n_spheres"], 2), np.float32)
        self.manifest["ticks"] = int(fr.shape[0])
        if extra_manifest:
            self.manifest.update(extra_manifest)
        fr.astype("<f4").tofile(self.dir / "frames.bin")
        ob.astype("<f4").tofile(self.dir / "objects.bin")
        (self.dir / "events.json").write_text(json.dumps(self.events, ensure_ascii=False), encoding="utf-8")
        (self.dir / "manifest.json").write_text(json.dumps(self.manifest, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        return self.dir


class Replay:
    def __init__(self, d: Path):
        self.dir = Path(d)
        self.manifest = json.loads((self.dir / "manifest.json").read_text(encoding="utf-8"))
        m = self.manifest
        self.fields = m["fields"]
        self.fi = {f: i for i, f in enumerate(self.fields)}
        self.frames = np.fromfile(self.dir / "frames.bin", dtype="<f4").reshape(m["ticks"], m["n_flies"], len(self.fields))
        self.objects = np.fromfile(self.dir / "objects.bin", dtype="<f4").reshape(m["ticks"], m["n_spheres"], 2)
        self.events = json.loads((self.dir / "events.json").read_text(encoding="utf-8"))

    def col(self, name: str) -> np.ndarray:
        return self.frames[:, :, self.fi[name]]

    @property
    def t(self) -> np.ndarray:
        return np.arange(self.manifest["ticks"]) * self.manifest["dt_s"]
