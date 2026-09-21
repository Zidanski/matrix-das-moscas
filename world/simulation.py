"""Simulacao de um "dia": 6 moscas, 6 processos (ate `max_concurrent` ativos), loop de 15 ms.

A cada tick:
  1. o mundo calcula o SensoryState de cada mosca (senses.py)
  2. cada cerebro roda 15 ms no seu processo e devolve o MotorState
  3. a fisica aplica os comandos e reage (physics.py); eventos sao registrados
  4. o replay grava pose, estado e taxas de todas as moscas
Nao existe roteiro: toda decisao vem dos neuronios.
"""

from __future__ import annotations

import math
import multiprocessing as mp
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from brain.types import OUTPUTS, INPUTS
from interface.config import load_config
from interface.motor import MotorState
from replay.format import ReplayWriter, STATE_IDS, LEVEL_IDS
from .geometry import Terrain, Objects, load_world
from .physics import Physics, FlyBody
from .senses import Senses
from .lab import Lab
from .robots import RobotFleet
from .secrets import Secrets
from .diary import write_diary


# ----------------------------------------------------------------------------
# processo de uma mosca
# ----------------------------------------------------------------------------
def _fly_worker(conn, pack_name: str, identity: dict, cfg: dict, control_seed: int | None):
    from brain.pack import ConnectomePack
    from brain.shuffle import shuffled_pack
    from interface.fly_brain import FlyBrain, FlyIdentity
    pack = ConnectomePack.load(pack_name)
    if control_seed is not None:
        pack = shuffled_pack(pack, control_seed)
    fly = FlyBrain(pack, FlyIdentity(**identity), cfg)
    conn.send({"ok": True, "hud": fly.hud_label, "n": pack.n, "missing": fly.encoder.missing})
    while True:
        msg = conn.recv()
        if msg is None:
            break
        state, hunger = msg
        fly.encoder.hunger_gain = hunger
        m = fly.step(state)
        conn.send({"motor": asdict(m), "ignited": fly.ignited, "spikes": fly.last_window_spikes})
    conn.close()


class RemoteFly:
    def __init__(self, pack_name, identity, cfg, control_seed=None):
        ctx = mp.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self.proc = ctx.Process(target=_fly_worker, args=(child, pack_name, identity, cfg, control_seed), daemon=True)
        self.proc.start()
        self.info = self.conn.recv()

    def send(self, state, hunger):
        self.conn.send((state, hunger))

    def recv(self):
        return self.conn.recv()

    def close(self):
        try:
            self.conn.send(None)
        except Exception:  # noqa: BLE001
            pass
        self.proc.join(timeout=5)


class LocalFly:
    """Mesma interface sem processo (testes e depuracao)."""

    def __init__(self, brain):
        self.brain = brain
        self.info = {"ok": True, "hud": getattr(brain, "hud_label", "local"), "n": 0, "missing": []}
        self._out = None

    def send(self, state, hunger):
        if hasattr(self.brain, "encoder"):
            self.brain.encoder.hunger_gain = hunger
        m = self.brain.step(state)
        self._out = {"motor": asdict(m), "ignited": getattr(self.brain, "ignited", False), "spikes": getattr(self.brain, "last_window_spikes", 0)}

    def recv(self):
        return self._out

    def close(self):
        pass


# ----------------------------------------------------------------------------
# o dia
# ----------------------------------------------------------------------------
class Day:
    def __init__(self, seconds: float, brain_mode: str = "reduced", out_dir: Path | str = "runs/day",
                 world_cfg: dict | None = None, iface_cfg: dict | None = None, control_fly: str | None = None,
                 fly_factory=None, day_index: int = 0, log=print):
        self.w = world_cfg or load_world()
        self.cfg = iface_cfg or load_config()
        self.seconds = float(seconds)
        self.dt = float(self.cfg["loop"]["dt_ms"]) / 1000.0
        self.brain_mode = brain_mode
        self.out_dir = Path(out_dir)
        self.control_fly = control_fly
        self.fly_factory = fly_factory
        self.day_index = day_index
        self.log = log
        self.terrain = Terrain(self.w["arena"]["hills"], self.w["arena"]["radius_cm"])
        self.objects = Objects.from_config(self.w)
        self.lab = Lab(self.w["lab"]) if "lab" in self.w else None
        self.physics = Physics(self.w, self.terrain, self.objects, self.lab)
        self.senses = Senses(self.w, self.objects)
        self.robots = RobotFleet(self.w) if self.lab else None
        self.secrets = Secrets(self.w, self.lab, self.objects) if self.lab else None
        rng = np.random.default_rng(1000 + day_index)
        self.bodies: list[FlyBody] = []
        for i, f in enumerate(self.w["flies"]):
            r = float(self.w["spawn_radius_cm"]) * math.sqrt(rng.random())
            a = rng.random() * 2 * math.pi
            self.bodies.append(FlyBody(f["name"], f["sex"], r * math.cos(a), r * math.sin(a), rng.random() * 2 * math.pi, idx=i))
        self.rate_pops = [p for p in OUTPUTS]
        self.stats = {}

    def _pack_for(self, sex: str) -> str:
        key = f"{sex}_{'full' if self.brain_mode == 'full' else 'reduced'}"
        return self.w["brains"][key]

    def _spawn_brains(self):
        flies = []
        for i, f in enumerate(self.w["flies"]):
            ident = {"name": f["name"], "sex": f["sex"], "color": f["color"], "seed": int(f["seed"]) + 100 * self.day_index,
                     "hunger_gain": 1.0, "control": f["name"] == self.control_fly}
            if self.fly_factory is not None:
                flies.append(LocalFly(self.fly_factory(ident)))
            else:
                flies.append(RemoteFly(self._pack_for(f["sex"]), ident, self.cfg, control_seed=(int(f["seed"]) if ident["control"] else None)))
            self.log(f"  {f['name']} ({f['sex']}): {flies[-1].info['hud']}")
        return flies

    def run(self) -> Path:
        t0 = time.time()
        flies = self._spawn_brains()
        n_ticks = int(round(self.seconds / self.dt))
        manifest = {"world": self.w, "interface": self.cfg, "dt_s": self.dt, "seconds": self.seconds,
                    "brain_mode": self.brain_mode, "day_index": self.day_index,
                    "flies": [{"name": b.name, "sex": b.sex, "color": self.w["flies"][b.idx]["color"], "hud": fl.info["hud"],
                               "n_neurons": fl.info["n"], "missing_inputs": fl.info["missing"], "control": self.w["flies"][b.idx]["name"] == self.control_fly}
                              for b, fl in zip(self.bodies, flies)],
                    "spheres": [asdict(s) for s in self.objects.spheres], "cubes": [asdict(c) for c in self.objects.cubes],
                    "prisms": [asdict(p) for p in self.objects.prisms], "patches": [asdict(p) for p in self.objects.patches],
                    "water": [asdict(w) for w in self.objects.water],
                    "robots": [{"name": r.name, "level": r.level, "route": r.route, "r": r.r, "night_only": r.night_only} for r in (self.robots.robots if self.robots else [])],
                    "n_robots": len(self.robots.robots) if self.robots else 0}
        writer = ReplayWriter(self.out_dir, manifest, self.rate_pops, len(self.bodies), len(self.objects.spheres), input_pops=INPUTS)
        songs = {b.name: False for b in self.bodies}
        loom_side = {b.name: 0.0 for b in self.bodies}
        prev_state = {b.name: "" for b in self.bodies}
        near = {}
        maxc = int(self.w["brains"]["max_concurrent"])
        ignited_total = {b.name: 0 for b in self.bodies}
        encounters = set()
        captures = {b.name: 0 for b in self.bodies}
        for k in range(n_ticks):
            t = k * self.dt
            self.physics.t = t
            robots = self.robots.robots if self.robots else []
            states = [self.senses.sense(b, self.bodies, songs, t, self.dt, robots) for b in self.bodies]
            for b, st in zip(self.bodies, states):
                l4 = st.get("lc4", (0.0, 0.0))
                loom_side[b.name] = l4[0] - l4[1]
            # round-robin: ate maxc cerebros ativos por vez
            outs = [None] * len(flies)
            for start in range(0, len(flies), maxc):
                grp = list(range(start, min(start + maxc, len(flies))))
                for i in grp:
                    flies[i].send(states[i], self.bodies[i].hunger_gain)
                for i in grp:
                    outs[i] = flies[i].recv()
            rows = []
            for b, out, st in zip(self.bodies, outs, states):
                m = MotorState(**out["motor"])
                if out["ignited"]:
                    ignited_total[b.name] += 1
                self.physics.apply_motor(b, m, self.dt, loom_side[b.name])
                if out["ignited"]:
                    b.state = "convulsao"
                self.physics.update_hunger(b, t, self.dt)
                songs[b.name] = bool(m.song) and b.sex == "male"
                if m.court and b.sex == "male" and b.state in ("andando", "parada", "cantando"):
                    b.state = "cortejando" if not m.song else "cantando"
                if b.state != prev_state[b.name]:
                    writer.add_event(t, "estado", [b.name], de=prev_state[b.name], para=b.state)
                    prev_state[b.name] = b.state
                if "agua_presa" in b.contacts:
                    writer.add_event(t, "presa_na_agua", [b.name])
                for c in b.contacts:
                    if c.startswith("bola") and any(s.name == c and s.pushes == 1 for s in self.objects.spheres):
                        writer.add_event(t, "esfera_empurrada", [b.name], objeto=c)
                    if c.startswith("entrou:"):
                        via = c.split(":")[1]
                        writer.add_event(t, "afundou" if via == "lago" else "entrou_no_lab", [b.name], via=via)
                if b.level == "lab":
                    b.time_in_lab += self.dt
                if m.jump and b.jump_t > 0.1:
                    writer.add_event(t, "salto", [b.name], loom=round(loom_side[b.name], 2))
                row = [b.x, b.y, b.z, b.heading, b.v, b.omega, STATE_IDS.get(b.state, 0), b.hunger_gain, float(out["ignited"]),
                       float(out["spikes"]), float(m.feed), float(m.jump), float(m.song), float(m.court), float(b.stuck), float(LEVEL_IDS[b.level])]
                r = m.rates_hz
                for p in self.rate_pops:
                    d = r.get(p, {"all": 0.0, "L": 0.0, "R": 0.0})
                    row += [d["all"], d["L"], d["R"]]
                for p in INPUTS:
                    l, rr = st.get(p, (0.0, 0.0))
                    row += [l, rr]
                rows.append(row)
            for a, o in self.physics.rescue_check(self.bodies):
                writer.add_event(t, "resgate_da_agua", [a, o])
            self.physics.step_objects(self.dt)
            # robos e segredos (reacoes do laboratorio)
            world_row = []
            if self.robots:
                light = self.senses.light(t)
                for e in self.robots.step(self.bodies, t, self.dt, light, self.lab.generator_off(t), self.lab, tuple(self.w["lab"]["exit_surface"])):
                    fl = [e["fly"]] if "fly" in e else []
                    if e["kind"] == "captura":
                        captures[e["fly"]] += 1
                    writer.add_event(t, e["kind"], fl, robot=e.get("robot"))
                for e in self.secrets.check(self.bodies, self.robots, songs, t):
                    writer.add_event(t, e["kind"], e.get("flies", []), secret=e.get("secret"))
                for r in self.robots.robots:
                    world_row += [r.x, r.y, float(r.level == "lab"), float({"patrulha": 0, "persegue": 1, "captura": 2, "carrega": 3, "congelado": 4, "dormindo": 5}[r.state])]
                world_row += self.lab.state_row(t)
            # encontros: pares a menos de 1 cm (registra inicio)
            enc = float(self.w["fly"]["encounter_cm"])
            for i in range(len(self.bodies)):
                for j in range(i + 1, len(self.bodies)):
                    bi, bj = self.bodies[i], self.bodies[j]
                    d = math.hypot(bi.x - bj.x, bi.y - bj.y)
                    key = (bi.name, bj.name)
                    if d < enc:
                        near[key] = near.get(key, 0.0) + self.dt
                        if key not in encounters:
                            encounters.add(key)
                            writer.add_event(t, "encontro", [bi.name, bj.name], sexos=f"{bi.sex[0]}{bj.sex[0]}")
                    else:
                        encounters.discard(key)
            writer.add_frame(rows, [(s.x, s.y) for s in self.objects.spheres], world_row)
            if k % max(1, n_ticks // 10) == 0:
                self.log(f"  t={t:5.1f}s  " + " ".join(f"{b.name}:{b.state[:4]}" for b in self.bodies) + f"  ({time.time()-t0:.0f} s)")
        for fl in flies:
            fl.close()
        self.stats = self._metrics(near, ignited_total)
        for b in self.bodies:
            self.stats[b.name]["tempo_no_subsolo_s"] = round(b.time_in_lab, 2)
            self.stats[b.name]["capturas"] = captures[b.name]
        secrets = self.secrets.summary() if self.secrets else {}
        self.stats["_dia"]["segredos"] = {k: {"quase": v["quase"], "disparou": v["disparou"]} for k, v in secrets.items() if isinstance(v, dict)}
        self.stats["_dia"]["fugiram"] = secrets.get("fugiram", [])
        diary = write_diary(self.day_index, self.seconds, manifest["flies"], self.stats, writer.events, secrets,
                            self.cfg.get("interventions"))
        (self.out_dir).mkdir(parents=True, exist_ok=True)
        (self.out_dir / "diario.md").write_text(diary, encoding="utf-8")
        d = writer.close({"metrics": self.stats, "wall_s": time.time() - t0, "secrets": secrets, "diary": diary})
        self.log(f"[dia {self.day_index}] {self.seconds:.0f} s bio em {time.time()-t0:.0f} s de parede -> {d}")
        return d

    def _metrics(self, near, ignited_total) -> dict:
        out = {}
        for b in self.bodies:
            close = sum(v for (a, o), v in near.items() if b.name in (a, o))
            out[b.name] = {"distancia_cm": round(b.distance, 2), "tempo_comendo_s": round(b.time_feeding, 2),
                           "tempo_perto_de_outra_s": round(close, 2), "ticks_convulsao": ignited_total[b.name],
                           "indice_agregacao": round(close / self.seconds, 3)}
        mf = [v for (a, o), v in near.items() if {self._sex(a), self._sex(o)} == {"male", "female"}]
        out["_dia"] = {"encontros_macho_femea_s": round(sum(mf), 2), "pares_mf_que_se_encontraram": len(mf),
                       "esferas_empurradas": sum(s.pushes > 0 for s in self.objects.spheres)}
        return out

    def _sex(self, name):
        return next(b.sex for b in self.bodies if b.name == name)
