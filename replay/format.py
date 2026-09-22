"""Formato de replay de um "dia".

runs/<dia>/
  manifest.json   mundo (config), moscas, campos, dt, ticks, cerebros (rotulo do HUD)
  frames.bin      float32 [ticks, n_moscas, n_campos] little-endian (pose, estado, taxas)
  objects.bin     float32 [ticks, n_esferas, 2] (x, y das esferas)
  events.json     lista de eventos {t, tipo, moscas, dados}
  spikes.bin      uint16: indices (na amostra) dos neuronios que dispararam, por (tick, mosca)
  spikes_ptr.bin  int32 [ticks*n_moscas+1]: inicio de cada (tick, mosca) em spikes.bin
  soma_<i>.bin    float32 [n_amostra, 4]: x, y, z normalizados em [-1,1] + classe (painel do cerebro)
O visualizador web le manifest.json + frames.bin com DataView.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

STATE_IDS = {"parada": 0, "andando": 1, "re": 2, "comendo": 3, "saltando": 4, "cantando": 5,
             "presa": 6, "convulsao": 7, "capturada": 8, "grooming": 9, "lutando": 10, "cortejando": 11,
             "dancando": 12, "flertando": 13, "passeando": 14, "jogando_bola": 15, "jogando_cartas": 16, "apostando": 17,
             "morta": 18, "pregando": 19, "ouvindo": 20}
STATE_NAMES = {v: k for k, v in STATE_IDS.items()}

BASE_FIELDS = ["x", "y", "z", "heading", "v", "omega", "state", "hunger", "ignited", "spikes", "feed", "jump", "song", "court", "stuck", "level",
               "gamified", "need_social", "need_fun", "need_romance"]
LEVEL_IDS = {"surface": 0, "lab": 1, "fora": 2}
ROBOT_FIELDS = ["x", "y", "level", "state"]          # por robo, por tick (world.bin)
LAB_FIELDS = ["door_s2", "hatch", "generator_off", "elevator_open"]   # estado dos mecanismos (world.bin)


class ReplayWriter:
    def __init__(self, out_dir: Path, manifest: dict, rate_pops: list[str], n_flies: int, n_spheres: int, input_pops: list[str] | None = None):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.rate_pops = rate_pops
        self.input_pops = input_pops or []
        self.fields = BASE_FIELDS + [f"rate_{p}_{s}" for p in rate_pops for s in ("all", "L", "R")] + [f"in_{p}_{s}" for p in self.input_pops for s in ("L", "R")]
        self.manifest = dict(manifest)
        self.n_robots = int(self.manifest.get("n_robots", 0))
        self.manifest.update({"fields": self.fields, "n_flies": n_flies, "n_spheres": n_spheres, "state_ids": STATE_IDS,
                              "level_ids": LEVEL_IDS, "robot_fields": ROBOT_FIELDS, "lab_fields": LAB_FIELDS})
        self.frames: list[np.ndarray] = []
        self.objs: list[np.ndarray] = []
        self.world_rows: list[np.ndarray] = []
        self.events: list[dict] = []
        self.spike_chunks: list[np.ndarray] = []
        self.spike_ptr: list[int] = [0]
        self.brain_samples: list[dict] = []

    def add_frame(self, fly_rows: list[list[float]], sphere_xy: list[tuple[float, float]], world_row: list[float] | None = None):
        self.frames.append(np.asarray(fly_rows, dtype=np.float32))
        self.objs.append(np.asarray(sphere_xy, dtype=np.float32).reshape(-1, 2))
        self.world_rows.append(np.asarray(world_row if world_row is not None else [], dtype=np.float32))

    def add_spikes(self, idx: np.ndarray):
        """Chamar uma vez por (tick, mosca), na ordem: indices (uint16) na amostra de somas."""
        a = np.asarray(idx, dtype=np.uint16)
        self.spike_chunks.append(a)
        self.spike_ptr.append(self.spike_ptr[-1] + len(a))

    def add_brain_sample(self, fly_index: int, soma_xyz: np.ndarray, classes: np.ndarray, class_names: list[str], n_total: int):
        """Nuvem de somas de uma mosca: coordenadas normalizadas + classe por ponto."""
        xyz = np.asarray(soma_xyz, dtype=np.float32)
        if len(xyz):
            lo, hi = xyz.min(0), xyz.max(0)
            span = float(max((hi - lo).max(), 1e-6))
            xyz = (xyz - (lo + hi) / 2) / span * 2.0
        arr = np.concatenate([xyz, np.asarray(classes, dtype=np.float32)[:, None]], axis=1).astype("<f4")
        arr.tofile(self.dir / f"soma_{fly_index}.bin")
        self.brain_samples.append({"fly": fly_index, "n": int(len(xyz)), "n_total": int(n_total), "class_names": class_names})

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
        wr = np.stack(self.world_rows) if self.world_rows and len(self.world_rows[0]) else np.zeros((0, 0), np.float32)
        wr.astype("<f4").tofile(self.dir / "world.bin")
        self.manifest["world_row_len"] = int(wr.shape[1]) if wr.ndim == 2 else 0
        if self.spike_chunks:
            np.concatenate(self.spike_chunks).astype("<u2").tofile(self.dir / "spikes.bin")
            np.asarray(self.spike_ptr, dtype="<i4").tofile(self.dir / "spikes_ptr.bin")
            self.manifest["spikes"] = {"n": int(self.spike_ptr[-1]), "per": "tick*n_flies+fly"}
        self.manifest["brain_samples"] = self.brain_samples
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
        sp = self.dir / "spikes_ptr.bin"
        if sp.exists():
            self.spike_ptr = np.fromfile(sp, dtype="<i4")
            self.spike_idx = np.fromfile(self.dir / "spikes.bin", dtype="<u2")
        else:
            self.spike_ptr, self.spike_idx = None, None
        wl = m.get("world_row_len", 0)
        wb = self.dir / "world.bin"
        self.world = np.fromfile(wb, dtype="<f4").reshape(m["ticks"], wl) if wl and wb.exists() else np.zeros((m["ticks"], 0), np.float32)

    def spikes(self, tick: int, fly: int) -> np.ndarray:
        if self.spike_ptr is None:
            return np.zeros(0, np.uint16)
        k = tick * self.manifest["n_flies"] + fly
        return self.spike_idx[self.spike_ptr[k]:self.spike_ptr[k + 1]]

    def soma(self, fly: int) -> np.ndarray:
        return np.fromfile(self.dir / f"soma_{fly}.bin", dtype="<f4").reshape(-1, 4)

    def col(self, name: str) -> np.ndarray:
        return self.frames[:, :, self.fi[name]]

    @property
    def t(self) -> np.ndarray:
        return np.arange(self.manifest["ticks"]) * self.manifest["dt_s"]
