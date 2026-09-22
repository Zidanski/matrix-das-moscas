"""Modo AO VIVO: simula um dia e transmite cada tick por WebSocket; recebe comandos do modo Deus.

uv run matrix live --seconds 120 --port 8765
Mensagens para o navegador (JSON): {"type":"hello", manifest...}, {"type":"tick", ...},
{"type":"changes", ...}, {"type":"end", ...}. Comandos do navegador: {"cmd": ..., ...}.
O dia tambem e gravado em runs/live/day_XXXX como qualquer outro.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from pathlib import Path

import numpy as np

from world.simulation import Day


class LiveServer:
    def __init__(self, seconds: float, brain: str, port: int, out: str, control: str | None):
        self.seconds, self.brain, self.port, self.out, self.control = seconds, brain, port, out, control
        self.clients: set = set()
        self.commands: queue.Queue = queue.Queue()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.hello: dict | None = None
        self.day: Day | None = None
        self.last_tick: dict | None = None

    # ---- lado da simulacao (thread) ----
    def on_tick(self, frame: dict):
        self.last_tick = frame
        msg = json.dumps({"type": "tick", **frame}, default=_np)
        self._broadcast(msg)

    def _broadcast(self, msg: str):
        if self.loop is None:
            return
        for ws in list(self.clients):
            asyncio.run_coroutine_threadsafe(_safe_send(ws, msg), self.loop)

    def run_sim(self):
        import itertools
        idx = 0
        while True:
            day_dir = Path(self.out) / f"day_{idx:04d}"
            if not (day_dir / "manifest.json").exists():
                break
            idx += 1
        self.day = Day(self.seconds, brain_mode=self.brain, out_dir=Path(self.out) / f"day_{idx:04d}", control_fly=self.control,
                       day_index=idx, on_tick=self.on_tick, commands=self.commands, log=lambda *a, **k: print(*a, flush=True))
        d = self.day
        d.flies = d._spawn_brains()
        self.hello = self._hello(d)
        self._broadcast(json.dumps({"type": "hello", **self.hello}, default=_np))
        # Day.run refaz _spawn_brains: evitamos duplicar substituindo o metodo
        flies = d.flies
        d._spawn_brains = lambda: flies
        d.run()
        self._broadcast(json.dumps({"type": "end", "dir": str(d.out_dir), "metrics": d.stats, "diary": d.stats and (d.out_dir / "diario.md").read_text(encoding="utf-8")}, default=_np))
        print("[ao vivo] dia gravado em", d.out_dir, flush=True)

    def _hello(self, d: Day) -> dict:
        from replay.format import BASE_FIELDS, STATE_IDS, LEVEL_IDS, ROBOT_FIELDS, LAB_FIELDS
        from brain.types import OUTPUTS, INPUTS
        from dataclasses import asdict
        fields = BASE_FIELDS + [f"rate_{p}_{s}" for p in OUTPUTS for s in ("all", "L", "R")] + [f"in_{p}_{s}" for p in INPUTS for s in ("L", "R")]
        return {"world": d.w, "interface": d.cfg, "dt_s": d.dt, "seconds": d.seconds, "brain_mode": d.brain_mode, "day_index": d.day_index,
                "fields": fields, "n_flies": len(d.bodies), "n_spheres": len(d.objects.spheres), "state_ids": STATE_IDS, "level_ids": LEVEL_IDS,
                "robot_fields": ROBOT_FIELDS, "lab_fields": LAB_FIELDS, "n_robots": len(d.robots.robots) if d.robots else 0,
                "world_row_len": (len(d.robots.robots) * 4 + 4) if d.robots else 0,
                "flies": [{"name": b.name, "sex": b.sex, "color": d.w["flies"][b.idx]["color"], "hud": fl.info["hud"], "n_neurons": fl.info["n"],
                           "missing_inputs": fl.info["missing"], "control": d.w["flies"][b.idx]["name"] == d.control_fly} for b, fl in zip(d.bodies, d.flies)],
                "spheres": [asdict(s) for s in d.objects.spheres], "cubes": [asdict(c) for c in d.objects.cubes], "prisms": [asdict(p) for p in d.objects.prisms],
                "patches": [asdict(p) for p in d.objects.patches], "water": [asdict(w) for w in d.objects.water],
                "robots": [{"name": r.name, "level": r.level, "route": r.route, "r": r.r, "night_only": r.night_only} for r in (d.robots.robots if d.robots else [])],
                "brain_samples": [{"fly": i, "n": len(fl.info["soma"]), "n_total": fl.info["n"], "class_names": fl.info["class_names"]} for i, fl in enumerate(d.flies)],
                "soma": [np.concatenate([_norm(fl.info["soma"]), np.asarray(fl.info["classes"], dtype=np.float32)[:, None]], axis=1).ravel().tolist() if len(fl.info["soma"]) else [] for fl in d.flies]}

    # ---- lado do WebSocket (asyncio) ----
    async def handler(self, ws):
        self.clients.add(ws)
        try:
            if self.hello:
                await ws.send(json.dumps({"type": "hello", **self.hello}, default=_np))
            async for raw in ws:
                try:
                    cmd = json.loads(raw)
                except Exception:  # noqa: BLE001
                    continue
                self.commands.put(cmd)
                await ws.send(json.dumps({"type": "ack", "cmd": cmd.get("cmd")}))
        except Exception:  # noqa: BLE001  (cliente fechou sem aviso)
            pass
        finally:
            self.clients.discard(ws)

    async def serve(self):
        import websockets
        self.loop = asyncio.get_running_loop()
        async with websockets.serve(self.handler, "localhost", self.port, max_size=None):
            print(f"[ao vivo] ws://localhost:{self.port}  (abra o visualizador e escolha AO VIVO)", flush=True)
            th = threading.Thread(target=self.run_sim, daemon=True)
            th.start()
            while th.is_alive():
                await asyncio.sleep(0.2)
            await asyncio.sleep(1.0)


def _norm(xyz):
    xyz = np.asarray(xyz, dtype=np.float32)
    if len(xyz) == 0:
        return xyz
    lo, hi = xyz.min(0), xyz.max(0)
    span = float(max((hi - lo).max(), 1e-6))
    return (xyz - (lo + hi) / 2) / span * 2.0


def _np(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return str(o)


async def _safe_send(ws, msg):
    try:
        await ws.send(msg)
    except Exception:  # noqa: BLE001
        pass


def main(args) -> int:
    srv = LiveServer(args.seconds, args.brain, args.port, args.out, args.control)
    asyncio.run(srv.serve())
    return 0
