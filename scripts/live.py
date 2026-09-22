"""Modo AO VIVO: servidor persistente controlado pelo navegador (WebSocket).

uv run matrix live --port 8765        (o `npm run dev` em web/ sobe isto sozinho)
Estados: idle -> running -> paused -> running -> ... -> stopping -> idle.
Comandos do navegador: {"cmd":"start"|"pause"|"resume"|"stop"|"reset"} e os do
modo Deus (mute, reset_brain, save_brain, restore_brain, ignite, add_food,
add_ball, add_robot, teleport, feed, set_need). Cada dia ao vivo corre sem fim
ate "stop"/"reset" e e gravado em runs/live/day_XXXX como qualquer outro.
Mensagens: {"type":"status"}, {"type":"hello"}, {"type":"tick"}, {"type":"end"}.
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

ENDLESS_S = 1e9


class LiveServer:
    def __init__(self, port: int, out: str, brain: str = "reduced", control: str | None = None):
        self.port, self.out, self.brain, self.control = port, out, brain, control
        self.clients: set = set()
        self.commands: queue.Queue = queue.Queue()      # para o Day (modo Deus, pause/resume)
        self.control_cmds: queue.Queue = queue.Queue()  # start/stop/reset (para o loop do servidor)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.hello: dict | None = None
        self.day: Day | None = None
        self.state = "idle"
        self.thread: threading.Thread | None = None

    # ---- transmissao ----
    def _broadcast(self, obj: dict):
        if self.loop is None:
            return
        msg = json.dumps(obj, default=_np)
        for ws in list(self.clients):
            asyncio.run_coroutine_threadsafe(_safe_send(ws, msg), self.loop)

    def set_state(self, st: str, **extra):
        self.state = st
        self._broadcast({"type": "status", "state": st, **extra})
        print(f"[ao vivo] {st}", flush=True)

    def on_tick(self, frame: dict):
        self._broadcast({"type": "tick", **frame})

    # ---- simulacao (thread) ----
    def run_day(self):
        idx = 0
        while (Path(self.out) / f"day_{idx:04d}" / "manifest.json").exists():
            idx += 1
        self.set_state("starting", day=idx)
        d = Day(ENDLESS_S, brain_mode=self.brain, out_dir=Path(self.out) / f"day_{idx:04d}", control_fly=self.control,
                day_index=idx, on_tick=self.on_tick, commands=self.commands, log=lambda *a, **k: print(*a, flush=True))
        self.day = d
        d.flies = d._spawn_brains()
        flies = d.flies
        d._spawn_brains = lambda: flies
        self.hello = self._hello(d)
        self._broadcast({"type": "hello", **self.hello})
        self.set_state("running", day=idx)
        d.run()
        diary = (d.out_dir / "diario.md").read_text(encoding="utf-8") if (d.out_dir / "diario.md").exists() else ""
        self._broadcast({"type": "end", "dir": str(d.out_dir), "metrics": d.stats, "diary": diary})
        print("[ao vivo] dia gravado em", d.out_dir, flush=True)
        self.day = None
        self.hello = None
        self.set_state("idle")

    def _hello(self, d: Day) -> dict:
        from replay.format import BASE_FIELDS, STATE_IDS, LEVEL_IDS, ROBOT_FIELDS, LAB_FIELDS
        from brain.types import OUTPUTS, INPUTS
        from dataclasses import asdict
        fields = BASE_FIELDS + [f"rate_{p}_{s}" for p in OUTPUTS for s in ("all", "L", "R")] + [f"in_{p}_{s}" for p in INPUTS for s in ("L", "R")]
        return {"world": d.w, "interface": d.cfg, "dt_s": d.dt, "seconds": 0.0, "brain_mode": d.brain_mode, "day_index": d.day_index,
                "fields": fields, "n_flies": len(d.bodies), "n_spheres": len(d.objects.spheres), "state_ids": STATE_IDS, "level_ids": LEVEL_IDS,
                "robot_fields": ROBOT_FIELDS, "lab_fields": LAB_FIELDS, "n_robots": len(d.robots.robots) if d.robots else 0,
                "world_row_len": (len(d.robots.robots) * 4 + 4) if d.robots else 0,
                "flies": [{"name": b.name, "sex": b.sex, "color": d.w["flies"][b.idx]["color"], "hud": fl.info["hud"], "n_neurons": fl.info["n"],
                           "missing_inputs": fl.info["missing"], "control": d.w["flies"][b.idx]["name"] == d.control_fly} for b, fl in zip(d.bodies, d.flies)],
                "spheres": [asdict(s) for s in d.objects.spheres], "cubes": [asdict(c) for c in d.objects.cubes], "prisms": [asdict(p) for p in d.objects.prisms],
                "patches": [asdict(p) for p in d.objects.patches], "water": [asdict(w) for w in d.objects.water],
                "playgrounds": [asdict(p) for p in d.objects.playgrounds],
                "robots": [{"name": r.name, "level": r.level, "route": r.route, "r": r.r, "night_only": r.night_only} for r in (d.robots.robots if d.robots else [])],
                "brain_samples": [{"fly": i, "n": len(fl.info["soma"]), "n_total": fl.info["n"], "class_names": fl.info["class_names"]} for i, fl in enumerate(d.flies)],
                "soma": [np.concatenate([_norm(fl.info["soma"]), np.asarray(fl.info["classes"], dtype=np.float32)[:, None]], axis=1).ravel().tolist() if len(fl.info["soma"]) else [] for fl in d.flies]}

    # ---- controle ----
    def handle_control(self, cmd: str):
        running = self.thread is not None and self.thread.is_alive()
        if cmd == "start" and not running:
            self.thread = threading.Thread(target=self.run_day, daemon=True)
            self.thread.start()
        elif cmd == "stop" and running and self.day is not None:
            self.set_state("stopping")
            self.commands.put({"cmd": "stop"})
        elif cmd == "reset":
            if running and self.day is not None:
                self.set_state("stopping")
                self.commands.put({"cmd": "stop"})
                self.thread.join(timeout=120)
            self.thread = threading.Thread(target=self.run_day, daemon=True)
            self.thread.start()
        elif cmd == "pause" and running:
            self.commands.put({"cmd": "pause"}); self.set_state("paused")
        elif cmd == "resume" and running:
            self.commands.put({"cmd": "resume"}); self.set_state("running")

    async def handler(self, ws):
        self.clients.add(ws)
        try:
            await ws.send(json.dumps({"type": "status", "state": self.state}))
            if self.hello:
                await ws.send(json.dumps({"type": "hello", **self.hello}, default=_np))
            async for raw in ws:
                try:
                    cmd = json.loads(raw)
                except Exception:  # noqa: BLE001
                    continue
                c = cmd.get("cmd")
                if c in ("start", "stop", "reset", "pause", "resume"):
                    threading.Thread(target=self.handle_control, args=(c,), daemon=True).start()
                else:
                    self.commands.put(cmd)
                await ws.send(json.dumps({"type": "ack", "cmd": c}))
        except Exception:  # noqa: BLE001
            pass
        finally:
            self.clients.discard(ws)

    async def serve(self):
        import websockets
        self.loop = asyncio.get_running_loop()
        async with websockets.serve(self.handler, "localhost", self.port, max_size=None):
            print(f"[ao vivo] servidor em ws://localhost:{self.port}; esperando 'start' do visualizador", flush=True)
            while True:
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
    srv = LiveServer(args.port, args.out, args.brain, args.control)
    asyncio.run(srv.serve())
    return 0
