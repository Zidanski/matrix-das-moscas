"""Fisica simples do mundo: corpos das moscas, colisoes, esferas que rolam, agua.

REGRA DE OURO: nada aqui decide para onde uma mosca vai. `apply_motor` so
converte o MotorState (lido dos neuronios descendentes) em deslocamento, e o
resto reage: parede, cubos, esferas empurradas, agua que prende.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geometry import Terrain, Objects, Sphere, wrap_angle
from .lab import Lab


@dataclass
class FlyBody:
    name: str
    sex: str
    x: float
    y: float
    heading: float
    z: float = 0.0
    v: float = 0.0            # cm/s efetivo (positivo frente, negativo re)
    omega: float = 0.0        # rad/s
    state: str = "parada"     # parada|andando|re|comendo|saltando|cantando|presa|convulsao|capturada
    stuck: bool = False       # presa na agua
    jump_t: float = 0.0       # tempo restante de salto
    jump_dir: float = 0.0
    hunger_gain: float = 1.0
    t_last_meal: float = 0.0
    distance: float = 0.0
    time_feeding: float = 0.0
    contacts: list = field(default_factory=list)   # o que tocou neste tick (nomes)
    on_surface: str = "none"                       # sugar|bitter|water|none (o que pisa/toca)
    idx: int = 0
    level: str = "surface"                         # surface | lab | fora (fugiu)
    stuck_since: float = -1.0
    time_in_lab: float = 0.0
    captures: int = 0


class Physics:
    def __init__(self, cfg: dict, terrain: Terrain, objects: Objects, lab: Lab | None = None):
        self.cfg = cfg
        self.f = cfg["fly"]
        self.terrain = terrain
        self.objects = objects
        self.R = float(cfg["arena"]["radius_cm"])
        self.lab = lab
        self.t = 0.0
        self.ramp = next((pr for pr in objects.prisms if pr.name == "prisma_co2"), None)
        self.hatch_cube = next((c for c in objects.cubes if c.hollow), None)

    # ---- movimento comandado pelos neuronios ----
    def apply_motor(self, b: FlyBody, m, dt: float, loom_side: float = 0.0) -> None:
        f = self.f
        b.contacts = []
        if b.level == "fora":
            return
        self._surfaces(b)          # o que a mosca toca AGORA decide se "comer" tem efeito
        if b.state == "capturada":
            b.v = 0.0; b.omega = 0.0
            return
        if b.jump_t > 0:
            b.jump_t -= dt
            b.v = float(f["jump_impulse_cm_s"])
            b.heading = b.jump_dir
            b.state = "saltando"
        elif m.jump:
            b.jump_t = float(f["jump_duration_s"])
            # salta para longe do lado do looming (loom_side > 0 = esquerda) ou para frente
            b.jump_dir = wrap_angle(b.heading + (-math.pi / 2 if loom_side > 0.05 else (math.pi / 2 if loom_side < -0.05 else 0.0)))
            b.v = float(f["jump_impulse_cm_s"])
            b.state = "saltando"
            b.stuck = False
        elif b.stuck:
            b.v = 0.0; b.omega = 0.0; b.state = "presa"
        elif m.feed and b.on_surface in ("sugar", "water"):
            b.v = 0.0; b.omega = 0.0; b.state = "comendo"
        elif m.halt:
            b.v = 0.0; b.omega = 0.0; b.state = "parada"
        elif m.backward_cm_s > 0:
            b.v = -float(m.backward_cm_s); b.omega = float(m.turn_rad_s); b.state = "re"
        else:
            b.v = float(m.forward_cm_s); b.omega = float(m.turn_rad_s)
            b.state = "andando" if abs(b.v) > 0.05 or abs(b.omega) > 0.1 else "parada"
        if m.song and b.state in ("parada", "andando"):
            b.state = "cantando"
        # integracao
        b.heading = wrap_angle(b.heading + b.omega * dt)
        nx = b.x + b.v * math.cos(b.heading) * dt
        ny = b.y + b.v * math.sin(b.heading) * dt
        nx, ny = self._collide(b, nx, ny, dt) if b.level == "surface" else self._collide_lab(b, nx, ny)
        b.distance += math.hypot(nx - b.x, ny - b.y)
        b.x, b.y = nx, ny
        b.z = self.terrain.height(b.x, b.y) if b.level == "surface" else 0.0
        self._surfaces(b)
        self._transitions(b)

    # ---- reacoes do mundo ----
    def _collide(self, b: FlyBody, nx: float, ny: float, dt: float) -> tuple[float, float]:
        # parede da arena
        d = math.hypot(nx, ny)
        if d > self.R - 0.2:
            b.contacts.append("parede")
            nx, ny = nx * (self.R - 0.2) / d, ny * (self.R - 0.2) / d
            b.v = 0.0
        # cubos: caixa alinhada; a mosca para na face
        for c in self.objects.cubes:
            h = c.half + 0.15
            if abs(nx - c.x) < h and abs(ny - c.y) < h:
                b.contacts.append(c.name)
                # empurra para fora pela face mais proxima
                dx, dy = nx - c.x, ny - c.y
                if abs(dx) > abs(dy):
                    nx = c.x + math.copysign(h, dx)
                else:
                    ny = c.y + math.copysign(h, dy)
                b.v = 0.0
        # esferas: empurra (massa pequena) e para na superficie
        for s in self.objects.spheres:
            dx, dy = nx - s.x, ny - s.y
            dist = math.hypot(dx, dy)
            if dist < s.r + 0.15:
                b.contacts.append(s.name)
                if abs(b.v) > 0.05 and b.state == "andando":
                    push = b.v * 0.6 / max(s.mass, 0.1) * 0.5
                    ang = math.atan2(-dy, -dx)  # da mosca para o centro da esfera
                    s.vx += push * math.cos(ang) * dt * 10
                    s.vy += push * math.sin(ang) * dt * 10
                    s.pushes += 1
                if dist > 1e-6:
                    nx, ny = s.x + dx / dist * (s.r + 0.15), s.y + dy / dist * (s.r + 0.15)
                b.v = 0.0
        return nx, ny

    def _collide_lab(self, b: FlyBody, nx: float, ny: float) -> tuple[float, float]:
        lab = self.lab
        x0, y0, x1, y1 = lab.bounds
        m = 0.2
        if nx < x0 + m or nx > x1 - m or ny < y0 + m or ny > y1 - m:
            b.contacts.append("parede_lab")
            nx = min(max(nx, x0 + m), x1 - m); ny = min(max(ny, y0 + m), y1 - m)
            b.v = 0.0
        for r in lab.obstacles(self.t):
            if r.contains(nx, ny, 0.15):
                b.contacts.append("porta_s2" if r is lab.door_s2 else "parede_lab")
                nx, ny = r.push_out(nx, ny, 0.15)
                b.v = 0.0
        return nx, ny

    def _transitions(self, b: FlyBody) -> None:
        """Reacoes do mundo que mudam de nivel: rampa, escotilha (S1), fundo do lago, elevador (S4 em secrets)."""
        if self.lab is None or b.level != "surface":
            return
        lab = self.lab
        if self.ramp is not None and math.hypot(b.x - self.ramp.x, b.y - self.ramp.y) < self.ramp.size * 0.8 and b.state in ("andando", "saltando"):
            b.level = "lab"; b.x, b.y = lab.entry("rampa"); b.contacts.append("entrou:rampa"); b.stuck = False
            return
        if self.hatch_cube is not None and lab.hatch_open(self.t) and self.hatch_cube.name in b.contacts:
            b.level = "lab"; b.x, b.y = lab.entry("escotilha"); b.contacts.append("entrou:escotilha")
            return
        if b.stuck and b.stuck_since >= 0 and self.t - b.stuck_since > float(self.cfg["lab"]["lake_sink_s"]):
            b.level = "lab"; b.x, b.y = lab.entry("lago"); b.stuck = False; b.stuck_since = -1.0; b.contacts.append("entrou:lago")

    def _surfaces(self, b: FlyBody) -> None:
        f = self.f
        b.on_surface = "none"
        cr = float(f["contact_radius_cm"])
        if b.level == "lab":
            sp = self.lab.sugar if self.lab else None
            if sp and math.hypot(b.x - sp["x"], b.y - sp["y"]) < sp["r"] + cr * 0.5:
                b.on_surface = "sugar"
            return
        if b.level != "surface":
            return
        for s in self.objects.spheres:
            if math.hypot(b.x - s.x, b.y - s.y) < s.r + cr and s.surface in ("sugar", "bitter"):
                b.on_surface = s.surface
        for p in self.objects.patches:
            if math.hypot(b.x - p.x, b.y - p.y) < p.r + cr * 0.5 and p.kind in ("sugar", "bitter"):
                b.on_surface = p.kind
        for w in self.objects.water:
            d = math.hypot(b.x - w.x, b.y - w.y)
            if d < w.r + cr * 0.5:
                b.on_surface = "water"
                if d < w.r - float(f["water_trap_depth_cm"]) and b.state != "saltando":
                    if not b.stuck:
                        b.contacts.append("agua_presa")
                        b.stuck_since = self.t
                    b.stuck = True

    def step_objects(self, dt: float) -> None:
        for s in self.objects.spheres:
            if abs(s.vx) + abs(s.vy) < 1e-4:
                s.vx = s.vy = 0.0
                continue
            s.x += s.vx * dt
            s.y += s.vy * dt
            s.vx *= math.exp(-dt / 0.8)
            s.vy *= math.exp(-dt / 0.8)
            d = math.hypot(s.x, s.y)
            if d > self.R - s.r:
                s.x, s.y = s.x * (self.R - s.r) / d, s.y * (self.R - s.r) / d
                s.vx = s.vy = 0.0

    def rescue_check(self, bodies: list[FlyBody]) -> list[tuple[str, str]]:
        """Mosca presa na agua fica livre quando outra encosta nela (contato -> fuga)."""
        freed = []
        for b in bodies:
            if not b.stuck:
                continue
            for o in bodies:
                if o is b or o.stuck or o.level != b.level:
                    continue
                if math.hypot(b.x - o.x, b.y - o.y) < 2 * float(self.f["contact_radius_cm"]):
                    b.stuck = False; b.stuck_since = -1.0
                    b.jump_t = float(self.f["jump_duration_s"])
                    b.jump_dir = math.atan2(b.y - 0.0, b.x - 0.0)  # para fora do lago (aproximacao: radial)
                    freed.append((b.name, o.name))
                    break
        return freed

    def update_hunger(self, b: FlyBody, t: float, dt: float) -> None:
        f = self.f
        if b.state == "comendo" and b.on_surface == "sugar":
            b.hunger_gain = 1.0
            b.t_last_meal = t
            b.time_feeding += dt
        else:
            b.hunger_gain = min(float(f["hunger_max"]), 1.0 + float(f["hunger_rise_per_s"]) * (t - b.t_last_meal))
