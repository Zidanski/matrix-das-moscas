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
import sys
from multiprocessing.connection import wait as mp_wait
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
from .social import SocialLayer
from .geometry import Patch, Sphere
from .robots import Robot


# ----------------------------------------------------------------------------
# processo de uma mosca
# ----------------------------------------------------------------------------
SOMA_SAMPLE_MAX = 20000
CLASS_NAMES = ["outro", "sensorial", "central", "optico", "descendente", "motor", "ascendente", "vnc", "kenyon"]


def _classify(neurons) -> np.ndarray:
    sc = neurons["super_class"].astype("string").fillna("").str.lower().to_numpy()
    cc = neurons["cell_class"].astype("string").fillna("").to_numpy()
    out = np.zeros(len(sc), dtype=np.uint8)
    for i, (a, c) in enumerate(zip(sc, cc)):
        if c == "Kenyon_Cell": out[i] = 8
        elif "sensory" in a: out[i] = 1
        elif a in ("central", "cb_intrinsic"): out[i] = 2
        elif a.startswith("optic") or a.startswith("ol_") or "visual" in a: out[i] = 3
        elif "descending" in a: out[i] = 4
        elif "motor" in a: out[i] = 5
        elif "ascending" in a: out[i] = 6
        elif a.startswith("vnc"): out[i] = 7
    return out


def _step_with_ignition(fly, state, pack):
    import numpy as np
    from brain.types import populations
    idx, rate = fly.encoder.encode(state)
    kc = populations(pack).get("kc", np.zeros(0, np.int32))
    extra = kc[: min(300, len(kc))] if len(kc) else np.arange(min(300, pack.n), dtype=np.int32)
    fly.engine.set_poisson(np.concatenate([idx, extra]).astype(np.int32), np.concatenate([rate, np.full(len(extra), 200.0)]))
    before = int(fly.engine.counts.sum())
    fly.engine.run(fly.dt_ms, record=False)
    fly.last_window_spikes = int(fly.engine.counts.sum()) - before
    # convulsao induzida pelo modo Deus: o estado e forcado durante a inducao (a ignicao natural
    # continua dependendo do limiar de disparos); os 300 KCs a 200 Hz garantem a tempestade visivel
    fly.ignited = True
    return fly.decoder.decode(fly.engine.counts, fly.dt_ms)


def _fly_worker(conn, pack_name: str, identity: dict, cfg: dict, control_seed: int | None):
    # prioridade abaixo do normal: o navegador (visualizador) e o processo do mundo ganham a CPU primeiro
    if sys.platform == "win32":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)   # BELOW_NORMAL_PRIORITY_CLASS
        except Exception:  # noqa: BLE001
            pass
    from brain.pack import ConnectomePack
    from brain.shuffle import shuffled_pack
    from interface.fly_brain import FlyBrain, FlyIdentity
    pack = ConnectomePack.load(pack_name)
    if control_seed is not None:
        pack = shuffled_pack(pack, control_seed)
    fly = FlyBrain(pack, FlyIdentity(**identity), cfg)
    # amostra de somas para o painel do cerebro (ate 20k neuronios com soma anotado)
    nrn = pack.neurons
    has = nrn["soma_x"].notna().to_numpy() if "soma_x" in nrn else np.zeros(pack.n, bool)
    cand = np.flatnonzero(has)
    rng = np.random.default_rng(0)
    sample = np.sort(rng.choice(cand, size=min(SOMA_SAMPLE_MAX, len(cand)), replace=False)) if len(cand) else np.zeros(0, np.int64)
    xyz = nrn.loc[sample, ["soma_x", "soma_y", "soma_z"]].to_numpy(dtype=np.float32) if len(sample) else np.zeros((0, 3), np.float32)
    classes = _classify(nrn.iloc[sample]) if len(sample) else np.zeros(0, np.uint8)
    conn.send({"ok": True, "hud": fly.hud_label, "n": pack.n, "missing": fly.encoder.missing,
               "soma": xyz, "classes": classes, "class_names": CLASS_NAMES})
    prev = fly.engine.counts.copy()
    saved = None
    ignite_left = 0                      # janelas de 15 ms que faltam da convulsao induzida
    while True:
        msg = conn.recv()
        if msg is None:
            break
        if isinstance(msg, dict):            # comando do modo Deus
            cmd = msg.get("cmd")
            eng = fly.engine
            if cmd == "reset":
                eng.reset(); fly.decoder.reader.reset(); prev = eng.counts.copy()
            elif cmd == "save":
                saved = {k: getattr(eng, k).copy() for k in ("v", "g", "rfc_end", "active", "act_list", "n_act", "ring", "ring_n", "counts")} | {"step": eng.step}
            elif cmd == "restore" and saved is not None:
                for k, v in saved.items():
                    if k == "step":
                        eng.step = v
                    else:
                        getattr(eng, k)[...] = v
                prev = eng.counts.copy()
            elif cmd == "ignite":
                ignite_left = 100            # 1,5 s de tempo do cerebro
            conn.send({"ok": True, "cmd": cmd, "saved": saved is not None})
            continue
        state, hunger = msg
        fly.encoder.hunger_gain = hunger
        if ignite_left > 0:                  # convulsao induzida: 300 neuronios centrais a 200 Hz
            ignite_left -= 1
            m = _step_with_ignition(fly, state, pack)
        else:
            m = fly.step(state)
        cnt = fly.engine.counts
        fired = np.flatnonzero(cnt[sample] > prev[sample]).astype(np.uint16) if len(sample) else np.zeros(0, np.uint16)
        prev = cnt.copy()
        conn.send({"motor": asdict(m), "ignited": fly.ignited, "spikes": fly.last_window_spikes, "fired": fired})
    conn.close()


class RemoteFly:
    def __init__(self, pack_name, identity, cfg, control_seed=None, wait: bool = True):
        ctx = mp.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self.proc = ctx.Process(target=_fly_worker, args=(child, pack_name, identity, cfg, control_seed), daemon=True)
        self.proc.start()
        self.info = self.conn.recv() if wait else None

    def wait_info(self):
        """Os 6 processos sobem em paralelo: primeiro todos os start(), depois os recv()."""
        if self.info is None:
            self.info = self.conn.recv()
        return self.info

    def send(self, state, hunger):
        self.conn.send((state, hunger))

    def recv(self):
        return self.conn.recv()

    def command(self, cmd: str) -> dict:
        self.conn.send({"cmd": cmd})
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
        self.info = {"ok": True, "hud": getattr(brain, "hud_label", "local"), "n": 0, "missing": [],
                     "soma": np.zeros((0, 3), np.float32), "classes": np.zeros(0, np.uint8), "class_names": CLASS_NAMES}
        self._out = None

    def send(self, state, hunger):
        if hasattr(self.brain, "encoder"):
            self.brain.encoder.hunger_gain = hunger
        m = self.brain.step(state)
        self._out = {"motor": asdict(m), "ignited": getattr(self.brain, "ignited", False), "spikes": getattr(self.brain, "last_window_spikes", 0), "fired": np.zeros(0, np.uint16)}

    def recv(self):
        return self._out

    def command(self, cmd: str) -> dict:
        return {"ok": True, "cmd": cmd}

    def close(self):
        pass


# ----------------------------------------------------------------------------
# o dia
# ----------------------------------------------------------------------------
class Day:
    def __init__(self, seconds: float, brain_mode: str = "reduced", out_dir: Path | str = "runs/day",
                 world_cfg: dict | None = None, iface_cfg: dict | None = None, control_fly: str | None = None,
                 fly_factory=None, day_index: int = 0, log=print, on_tick=None, commands=None, realtime: bool = False):
        self.w = world_cfg or load_world()
        # modo tempo real (ao vivo): o mundo anda no relogio de parede; cada cerebro processa as
        # janelas de 15 ms que conseguir, em paralelo, e pula as outras (motor mantido). Marcado
        # por tick no campo brain_step. Fora do ao vivo (simulate) e sempre sincrono e exato.
        self.realtime = bool(realtime)
        self._rt_busy: dict = {}          # conn -> indice da mosca em calculo
        self._rt_last: dict = {}          # indice -> ultima saida do cerebro
        self._rt_sent: dict = {}          # indice -> tick do ultimo envio
        self._rt_steps: dict = {}         # indice -> janelas processadas
        self._rt_cmds: dict = {}          # indice -> comandos do modo Deus esperando o cerebro ficar livre
        self.rt_speed = 1.0               # ritmo do mundo em relacao ao relogio de parede (0,25x ... 1x), so no tempo real
        self._wall0: float | None = None  # origem do relogio de parede (None = recalcular)
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
        self.social = SocialLayer(self.w, self.bodies, seed=day_index)
        self.on_tick = on_tick            # modo ao vivo: chamado a cada tick com o quadro
        self.commands = commands          # fila de comandos do modo Deus (objetos com get_nowait)
        self.paused = False
        self.stop = False
        self.flies = []
        self.writer = None
        self.world_changes: list[dict] = []
        self.pending_events: list = []

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
                flies.append(RemoteFly(self._pack_for(f["sex"]), ident, self.cfg, control_seed=(int(f["seed"]) if ident["control"] else None), wait=False))
        for f, fl in zip(self.w["flies"], flies):
            if hasattr(fl, "wait_info"):
                fl.wait_info()
            self.log(f"  {f['name']} ({f['sex']}): {fl.info['hud']}")
        return flies

    # ------------------------------------------------------------ tempo real
    def _rt_dispatch_cmds(self, flies, i):
        for kind in self._rt_cmds.pop(i, []):
            flies[i].command(kind)

    def _brains_realtime(self, flies, conns, states, k, maxc):
        """Nao espera ninguem: recolhe o que terminou, manda o proximo lote, mantem o motor de quem esta calculando."""
        busy, last, sent = self._rt_busy, self._rt_last, self._rt_sent
        fresh = set()
        for c in (mp_wait(list(busy), timeout=0) if busy else []):
            i = busy.pop(c)
            last[i] = flies[i].recv()
            fresh.add(i)
            self._rt_steps[i] = self._rt_steps.get(i, 0) + 1
            self._rt_dispatch_cmds(flies, i)
        idle = sorted((i for i in range(len(flies)) if conns[i] not in busy and not self.bodies[i].dead), key=lambda i: sent.get(i, -1))
        for i in idle:
            if len(busy) >= maxc:
                break
            flies[i].send(states[i], self.bodies[i].hunger_gain)
            busy[conns[i]] = i
            sent[i] = k
        outs = []
        for i in range(len(flies)):
            o = dict(last.get(i) or {"motor": asdict(MotorState()), "ignited": False, "spikes": 0, "fired": np.zeros(0, np.uint16)})
            o["stepped"] = i in fresh
            if not o["stepped"]:
                m = dict(o["motor"]); m["jump"] = False        # o salto e de um tick so: nao repete enquanto o cerebro calcula
                o["motor"] = m
                o["fired"] = np.zeros(0, np.uint16)
            outs.append(o)
        return outs

    def run(self) -> Path:
        t0 = time.time()
        flies = self._spawn_brains()
        self.flies = flies
        n_ticks = int(round(self.seconds / self.dt))
        manifest = {"world": self.w, "interface": self.cfg, "dt_s": self.dt, "seconds": self.seconds,
                    "brain_mode": self.brain_mode, "day_index": self.day_index, "realtime": self.realtime,
                    "flies": [{"name": b.name, "sex": b.sex, "color": self.w["flies"][b.idx]["color"], "hat": self.w["flies"][b.idx].get("hat", ""), "hud": fl.info["hud"],
                               "n_neurons": fl.info["n"], "missing_inputs": fl.info["missing"], "control": self.w["flies"][b.idx]["name"] == self.control_fly}
                              for b, fl in zip(self.bodies, flies)],
                    "spheres": [asdict(s) for s in self.objects.spheres], "cubes": [asdict(c) for c in self.objects.cubes],
                    "prisms": [asdict(p) for p in self.objects.prisms], "patches": [asdict(p) for p in self.objects.patches],
                    "water": [asdict(w) for w in self.objects.water],
                    "playgrounds": [asdict(p) for p in self.objects.playgrounds],
                    "robots": [{"name": r.name, "level": r.level, "route": r.route, "r": r.r, "night_only": r.night_only} for r in (self.robots.robots if self.robots else [])],
                    "n_robots": len(self.robots.robots) if self.robots else 0}
        writer = ReplayWriter(self.out_dir, manifest, self.rate_pops, len(self.bodies), len(self.objects.spheres), input_pops=INPUTS)
        self.writer = writer
        for (pt, pk, pf, pd) in self.pending_events:
            writer.add_event(pt, pk, pf, **pd)
        self.pending_events = []
        for i, fl in enumerate(flies):
            writer.add_brain_sample(i, fl.info["soma"], fl.info["classes"], fl.info["class_names"], fl.info["n"])
        songs = {b.name: False for b in self.bodies}
        loom_side = {b.name: 0.0 for b in self.bodies}
        prev_state = {b.name: "" for b in self.bodies}
        near = {}
        maxc = int(self.w["brains"]["max_concurrent"])
        ignited_total = {b.name: 0 for b in self.bodies}
        encounters = set()
        captures = {b.name: 0 for b in self.bodies}
        deaths: dict[str, float] = {}
        starve_s = float(self.physics.f.get("starve_after_s", 0) or 0)
        starve_lab_only = bool(self.physics.f.get("starve_only_in_lab", True))
        last_stuck: dict[str, float] = {}
        k = -1
        self._wall0 = time.time()
        while k + 1 < n_ticks and not self.stop:
            k += 1
            t = k * self.dt
            self.physics.t = t
            self._process_commands(t)
            if self.paused:
                while self.paused and not self.stop:
                    self._process_commands(t)
                    time.sleep(0.05)
                self._wall0 = None
            if self.realtime:
                # relogio de parede (dividido pelo ritmo escolhido): espera se adiantou; se atrasou
                # mais de 1 s, nao tenta recuperar em rajada
                step = self.dt / max(0.05, self.rt_speed)
                now = time.time()
                if self._wall0 is None:
                    self._wall0 = now - k * step
                target = self._wall0 + k * step
                if now < target:
                    time.sleep(target - now)
                elif now - target > 1.0:
                    self._wall0 = now - k * step
            robots = self.robots.robots if self.robots else []
            states = [self.senses.sense(b, self.bodies, songs, t, self.dt, robots) for b in self.bodies]
            for b, st in zip(self.bodies, states):
                l4 = st.get("lc4", (0.0, 0.0))
                loom_side[b.name] = l4[0] - l4[1]
            # ate maxc cerebros ativos por vez. Escalonamento dinamico: assim que um
            # processo devolve, o proximo entra (machos, mais lentos, primeiro), em vez
            # de grupos fixos que esperam o mais lento de cada grupo.
            outs = [None] * len(flies)
            conns = [getattr(f, "conn", None) for f in flies]
            if self.realtime and all(c is not None for c in conns):
                outs = self._brains_realtime(flies, conns, states, k, maxc)
            elif all(c is not None for c in conns) and len(flies) > maxc:
                pending = sorted(range(len(flies)), key=lambda i: self.bodies[i].sex != "male")
                inflight: dict = {}
                while pending or inflight:
                    while pending and len(inflight) < maxc:
                        i = pending.pop(0)
                        flies[i].send(states[i], self.bodies[i].hunger_gain)
                        inflight[conns[i]] = i
                    for c in mp_wait(list(inflight)):
                        i = inflight.pop(c)
                        outs[i] = flies[i].recv()
            else:
                for start in range(0, len(flies), maxc):
                    grp = list(range(start, min(start + maxc, len(flies))))
                    for i in grp:
                        flies[i].send(states[i], self.bodies[i].hunger_gain)
                    for i in grp:
                        outs[i] = flies[i].recv()
            # camada social gamificada: assume quando o cerebro esta ocioso
            motors = {b.name: MotorState(**out["motor"]) if not b.dead else MotorState() for b, out in zip(self.bodies, outs)}
            overrides, social_events = self.social.step(self.bodies, motors, self.objects.spheres, t, self.dt)
            for e in social_events:
                writer.add_event(t, e["kind"], e["flies"], **{kk: v for kk, v in e.items() if kk not in ("kind", "flies")})
            rows = []
            for b, out, st in zip(self.bodies, outs, states):
                writer.add_spikes(out.get("fired", np.zeros(0, np.uint16)))
                m = motors[b.name]
                gamified = 0.0
                if b.name in overrides:
                    m = overrides[b.name]
                    gamified = 1.0
                if out["ignited"]:
                    ignited_total[b.name] += 1
                self.physics.apply_motor(b, m, self.dt, loom_side[b.name])
                if out["ignited"]:
                    b.state = "convulsao"
                self.physics.update_hunger(b, t, self.dt)
                # fome mortal (gamificado): so no subsolo, onde nao ha comida; capturada e excecao (o robo a alimenta)
                # conta so o tempo passado no subsolo sem comer (na superficie ha comida; a capturada e alimentada)
                if b.state != "capturada" and not b.dead and (b.level == "lab" or not starve_lab_only) and b.level != "fora":
                    b.lab_hunger_s += self.dt
                if starve_s > 0 and not b.dead and b.lab_hunger_s > starve_s:
                    b.dead = True; b.t_death = t; b.state = "morta"; b.v = 0.0; b.omega = 0.0
                    deaths[b.name] = t
                    writer.add_event(t, "morreu_de_fome", [b.name], sem_comer_s=round(b.lab_hunger_s, 1), onde=b.level)
                songs[b.name] = bool(m.song) and b.sex == "male"
                if m.court and b.sex == "male" and b.state in ("andando", "parada", "cantando"):
                    b.state = "cortejando" if not m.song else "cantando"
                if b.state != prev_state[b.name]:
                    writer.add_event(t, "estado", [b.name], de=prev_state[b.name], para=b.state)
                    prev_state[b.name] = b.state
                if "agua_presa" in b.contacts and t - last_stuck.get(b.name, -1e9) > 3.0:
                    last_stuck[b.name] = t
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
                    src, val = b.loom_source
                    jo = max(st.get("jo_a", (0, 0)) + st.get("jo_b", (0, 0)))
                    if val > 0.15:
                        who = src
                        motivo = f"vulto de {who}" + (" (robô)" if who.startswith("R") and who[1:].isdigit() else (" (bola rolando)" if who.startswith("bola") else " (mosca se aproximando)"))
                    elif jo > 0.3:
                        motivo = "barulho da canção perto da antena"
                    else:
                        motivo = "sobressalto espontâneo (disparo isolado da fibra gigante)"
                    writer.add_event(t, "salto", [b.name], loom=round(loom_side[b.name], 2), motivo=motivo)
                row = [b.x, b.y, b.z, b.heading, b.v, b.omega, STATE_IDS.get(b.state, 0), b.hunger_gain, float(out["ignited"]),
                       float(out["spikes"]), float(m.feed), float(m.jump), float(m.song), float(m.court), float(b.stuck), float(LEVEL_IDS[b.level]),
                       gamified] + self.social.rows(b.name) + [float(out.get("stepped", True))]
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
                    if e["kind"] == "soltura":
                        # o robo a alimentou la embaixo (excecao da fome) e ela volta "iluminada", contando do mundo magico
                        bb = next((x for x in self.bodies if x.name == e["fly"]), None)
                        if bb is not None:
                            bb.t_last_meal = t; bb.hunger_gain = 1.0; bb.lab_hunger_s = 0.0
                            bb.enlightened = True; bb.enlightened_t = t
                            self.social.enlighten(bb.name, t)
                            writer.add_event(t, "voltou_iluminada", [bb.name], robot=e.get("robot"))
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
            writer.add_frame(rows, [(s.x, s.y) for s in self.objects.spheres[:writer.manifest["n_spheres"]]], world_row)
            if self.on_tick is not None:
                self.on_tick({"tick": k, "t": t, "rows": rows, "spheres": [(s.x, s.y) for s in self.objects.spheres], "world": world_row,
                              "fired": [out.get("fired", np.zeros(0, np.uint16)).tolist() for out in outs],
                              "events": [e for e in writer.events if e["t"] == round(t, 3)], "light": self.senses.light(t),
                              "changes": self.world_changes})
                self.world_changes = []
            if k % max(1, n_ticks // 10) == 0:
                self.log(f"  t={t:5.1f}s  " + " ".join(f"{b.name}:{b.state[:4]}" for b in self.bodies) + f"  ({time.time()-t0:.0f} s)")
        for fl in flies:
            fl.close()
        # dias sem fim (ao vivo) ou interrompidos: a duracao real e a gravada
        self.seconds = float((k + 1) * self.dt) if k >= 0 else 0.0
        manifest["seconds"] = self.seconds
        self.stats = self._metrics(near, ignited_total)
        for b in self.bodies:
            self.stats[b.name]["tempo_no_subsolo_s"] = round(b.time_in_lab, 2)
            self.stats[b.name]["capturas"] = captures[b.name]
            self.stats[b.name]["morreu_de_fome_s"] = deaths.get(b.name)
            if self.realtime:
                self.stats[b.name]["janelas_do_cerebro"] = int(self._rt_steps.get(b.idx, 0))
                self.stats[b.name]["fracao_de_ticks_com_cerebro"] = round(self._rt_steps.get(b.idx, 0) / max(1, k + 1), 3)
            self.stats[b.name]["iluminada"] = bool(b.enlightened)
        secrets = self.secrets.summary() if self.secrets else {}
        self.stats["_dia"]["social"] = self.social.summary()
        self.stats["_dia"]["segredos"] = {k: {"quase": v["quase"], "disparou": v["disparou"]} for k, v in secrets.items() if isinstance(v, dict)}
        self.stats["_dia"]["fugiram"] = secrets.get("fugiram", [])
        self.stats["_dia"]["mortes"] = deaths
        self.stats["_dia"]["tempo_real"] = self.realtime
        if self.realtime:
            self.stats["_dia"]["ritmo_parede"] = round(self.seconds / max(1e-6, time.time() - t0), 3)
        diary = write_diary(self.day_index, self.seconds, manifest["flies"], self.stats, writer.events, secrets,
                            self.cfg.get("interventions"))
        (self.out_dir).mkdir(parents=True, exist_ok=True)
        (self.out_dir / "diario.md").write_text(diary, encoding="utf-8")
        d = writer.close({"metrics": self.stats, "wall_s": time.time() - t0, "secrets": secrets, "diary": diary, "seconds": self.seconds})
        self.log(f"[dia {self.day_index}] {self.seconds:.0f} s bio em {time.time()-t0:.0f} s de parede -> {d}")
        return d

    # ------------------------------------------------------------ modo Deus
    def _process_commands(self, t: float):
        if self.commands is None:
            return
        while True:
            try:
                cmd = self.commands.get_nowait()
            except Exception:  # noqa: BLE001
                return
            self.apply_command(cmd, t)

    def apply_command(self, cmd: dict, t: float) -> dict:
        kind = cmd.get("cmd")
        fly = cmd.get("fly")
        body = next((b for b in self.bodies if b.name == fly), None)
        idx = body.idx if body else None
        res = {"ok": True, "cmd": kind}
        if kind == "speed":
            self.rt_speed = max(0.1, min(4.0, float(cmd.get("value", 1.0))))
            self._wall0 = None
        elif kind == "pause":
            self.paused = True
        elif kind == "resume":
            self.paused = False
        elif kind == "stop":
            self.stop = True; self.paused = False
        elif kind == "mute":
            self.senses.mute[cmd.get("channel", "song")] = bool(cmd.get("on", True))
        elif kind in ("reset_brain", "save_brain", "restore_brain", "ignite") and idx is not None:
            mapped = {"reset_brain": "reset", "save_brain": "save", "restore_brain": "restore", "ignite": "ignite"}[kind]
            if self.realtime and getattr(self.flies[idx], "conn", None) in self._rt_busy:
                self._rt_cmds.setdefault(idx, []).append(mapped)     # o cerebro esta calculando: aplica quando devolver
                res = {"ok": True, "cmd": mapped, "queued": True}
            else:
                res = self.flies[idx].command(mapped)
        elif kind == "add_food":
            x, y = float(cmd.get("x", 0.0)), float(cmd.get("y", 0.0))
            pch = Patch(f"comida_deus_{len(self.objects.patches)}", x, y, 1.2, "sugar", 6.0)
            self.objects.patches.append(pch)
            self.world_changes.append({"type": "patch", "x": x, "y": y, "r": 1.2, "kind": "sugar", "name": pch.name})
        elif kind == "add_ball":
            x, y = float(cmd.get("x", 0.0)), float(cmd.get("y", 0.0))
            sp = Sphere(f"bola_deus_{len(self.objects.spheres)}", x, y, 1.0, cmd.get("surface", "none"), 0.4)
            self.objects.spheres.append(sp)
            self.world_changes.append({"type": "sphere", "x": x, "y": y, "r": 1.0, "surface": sp.surface, "name": sp.name})
        elif kind == "add_robot" and self.robots is not None:
            level = cmd.get("level", "surface")
            route = [[-8, -8], [8, -8], [8, 8], [-8, 8]] if level == "surface" else [[-16, -10], [-4, -10], [-4, 10], [-16, 10]]
            rc = self.w["lab"]["robots"]
            r = Robot.from_cfg({"name": f"R{len(self.robots.robots) + 1}", "level": level, "route": route}, rc)
            self.robots.robots.append(r)
            self.world_changes.append({"type": "robot", "name": r.name, "level": level, "route": route, "r": r.r})
        elif kind == "teleport" and body is not None:
            body.x, body.y = float(cmd.get("x", 0.0)), float(cmd.get("y", 0.0)); body.level = cmd.get("level", "surface"); body.stuck = False
        elif kind == "feed" and body is not None:
            body.hunger_gain = 1.0; body.t_last_meal = t
        elif kind == "revive" and body is not None:
            ex = tuple(self.w["lab"]["exit_surface"])
            body.dead = False; body.t_death = -1.0; body.state = "parada"; body.hunger_gain = 1.0; body.t_last_meal = t; body.lab_hunger_s = 0.0
            body.level = "surface"; body.x, body.y = float(ex[0]), float(ex[1]); body.stuck = False
        elif kind == "set_need" and body is not None:
            n = self.social.needs[body.name]
            setattr(n, cmd.get("need", "social"), float(cmd.get("value", 1.0)))
        else:
            res = {"ok": False, "cmd": kind, "erro": "comando desconhecido ou mosca invalida"}
        if self.writer is not None:
            self.writer.add_event(t, "modo_deus", [fly] if fly else [], comando=kind)
        else:
            self.pending_events.append((t, "modo_deus", [fly] if fly else [], {"comando": kind}))
        return res

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
