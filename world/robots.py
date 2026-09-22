"""Robos do laboratorio: maquinas de estado, sem IA.

Estados: PATRULHA (segue a rota) -> PERSEGUE (mosca no mesmo nivel a menos de
detect_cm) -> CAPTURA (contato continuo por capture_contact_s sem a mosca
saltar) -> CARREGA (leva a mosca ate o elevador e a solta na superficie) ->
PATRULHA. Gerador desligado (S3) = CONGELADO. Robos noturnos so saem quando
luz < 0.3. O unico "poder" deles e fisico: aproximar-se (looming), bloquear
(corpo solido) e carregar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Robot:
    name: str
    level: str
    route: list
    x: float = 0.0
    y: float = 0.0
    r: float = 1.2
    speed: float = 1.5
    night_only: bool = False
    state: str = "patrulha"       # patrulha|persegue|captura|carrega|congelado|dormindo
    wp: int = 0
    target: str | None = None
    contact_t: float = 0.0
    carrying: str | None = None
    active: bool = True
    heading: float = 0.0
    v: float = 0.0
    is_robot: bool = True
    sex: str = "robot"
    stuck: bool = False

    @classmethod
    def from_cfg(cls, c: dict, rcfg: dict) -> "Robot":
        route = [tuple(map(float, p)) for p in c["route"]]
        return cls(c["name"], c["level"], route, x=route[0][0], y=route[0][1], r=float(rcfg["radius_cm"]),
                   speed=float(rcfg["speed_cm_s"]), night_only=bool(c.get("night_only", False)),
                   state="dormindo" if c.get("night_only") else "patrulha", active=not c.get("night_only", False))

    def _move_towards(self, tx: float, ty: float, dt: float) -> float:
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        if d < 1e-6:
            self.v = 0.0
            return 0.0
        step = min(d, self.speed * dt)
        self.x += dx / d * step
        self.y += dy / d * step
        self.heading = math.atan2(dy, dx)
        self.v = step / dt
        return d - step


class RobotFleet:
    def __init__(self, cfg: dict):
        rc = cfg["lab"]["robots"]
        self.cfg = rc
        self.robots = [Robot.from_cfg(c, rc) for c in rc["patrol"]]
        self.detect = float(rc["detect_cm"])
        self.capture_s = float(rc["capture_contact_s"])

    def step(self, bodies: list, t: float, dt: float, light: float, generator_off: bool, lab, exit_surface: tuple) -> list[dict]:
        events = []
        for r in self.robots:
            if r.night_only:
                want = light < 0.3
                if want and not r.active:
                    r.active = True; r.state = "patrulha"; events.append({"kind": "robo_sai", "robot": r.name})
                elif not want and r.active and r.state in ("patrulha", "persegue"):
                    r.active = False; r.state = "dormindo"; r.x, r.y = r.route[0]; events.append({"kind": "robo_recolhe", "robot": r.name})
            if not r.active:
                continue
            if generator_off and r.state != "carrega":
                if r.state != "congelado":
                    events.append({"kind": "robo_congelado", "robot": r.name})
                r.state = "congelado"; r.v = 0.0
                continue
            if r.state == "congelado":
                r.state = "patrulha"
            same = [b for b in bodies if b.level == r.level and b.state not in ("capturada", "morta") and not getattr(b, "dead", False)]
            if r.state == "patrulha":
                tx, ty = r.route[r.wp]
                if r._move_towards(tx, ty, dt) < 0.1:
                    r.wp = (r.wp + 1) % len(r.route)
                near = [b for b in same if math.hypot(b.x - r.x, b.y - r.y) < self.detect]
                if near:
                    r.target = min(near, key=lambda b: math.hypot(b.x - r.x, b.y - r.y)).name
                    r.state = "persegue"; r.contact_t = 0.0
                    events.append({"kind": "robo_persegue", "robot": r.name, "fly": r.target})
            elif r.state == "persegue":
                b = next((b for b in same if b.name == r.target), None)
                if b is None or math.hypot(b.x - r.x, b.y - r.y) > self.detect * 1.5:
                    r.state = "patrulha"; r.target = None
                    continue
                d = r._move_towards(b.x, b.y, dt)
                if d < r.r + 0.4:
                    if b.state == "saltando":
                        r.contact_t = 0.0
                    else:
                        r.contact_t += dt
                    if r.contact_t >= self.capture_s:
                        r.state = "carrega"; r.carrying = b.name
                        b.state = "capturada"
                        events.append({"kind": "captura", "robot": r.name, "fly": b.name})
                else:
                    r.contact_t = 0.0
            elif r.state == "carrega":
                b = next((b for b in bodies if b.name == r.carrying), None)
                if b is None:
                    r.state = "patrulha"; r.carrying = None
                    continue
                goal = (lab.elevator.x, lab.elevator.y) if r.level == "lab" else exit_surface
                d = r._move_towards(goal[0], goal[1], dt)
                b.x, b.y = r.x, r.y
                if d < 0.3:
                    # solta na superficie (o elevador de servico leva o robo e volta)
                    b.level = "surface"; b.x, b.y = exit_surface; b.state = "parada"; b.stuck = False
                    events.append({"kind": "soltura", "robot": r.name, "fly": b.name})
                    r.state = "patrulha"; r.carrying = None; r.target = None
                    if r.level == "lab":
                        r.x, r.y = r.route[0]
        return events

    def rows(self) -> list[tuple[float, float, float, float]]:
        return [(r.x, r.y, float(r.level == "lab"), {"patrulha": 0, "persegue": 1, "captura": 2, "carrega": 3, "congelado": 4, "dormindo": 5}[r.state]) for r in self.robots]

    def chasing(self, fly_name: str) -> bool:
        return any(r.state == "persegue" and r.target == fly_name for r in self.robots)
