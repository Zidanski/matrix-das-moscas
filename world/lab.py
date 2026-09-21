"""O laboratorio (subsolo): geometria, portas, entradas e saidas.

Dois niveis: 'surface' (arena circular) e 'lab' (retangulo com paredes).
As transicoes sao reacoes fisicas a onde a mosca esta:
  rampa      -> tocar o prisma-rampa na superficie leva ao corredor de chegada
  escotilha  -> tocar o cubo oco enquanto a escotilha esta aberta (S1) cai na sala dos robos
  lago       -> presa na agua por lake_sink_s sem resgate: afunda para o subsolo
  elevador   -> S4: 3+ moscas dentro com a porta aberta = fuga ("fora")
  robo       -> captura: o robo carrega a mosca de volta a superficie
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def contains(self, px: float, py: float, margin: float = 0.0) -> bool:
        return abs(px - self.x) < self.w / 2 + margin and abs(py - self.y) < self.h / 2 + margin

    def push_out(self, px: float, py: float, margin: float) -> tuple[float, float]:
        dx, dy = px - self.x, py - self.y
        ox = self.w / 2 + margin - abs(dx)
        oy = self.h / 2 + margin - abs(dy)
        if ox < oy:
            return self.x + math.copysign(self.w / 2 + margin, dx), py
        return px, self.y + math.copysign(self.h / 2 + margin, dy)


@dataclass
class Lab:
    cfg: dict
    bounds: tuple = (0, 0, 0, 0)
    walls: list = field(default_factory=list)
    door_s2: Rect | None = None
    door_open_until: float = -1.0
    hatch_open_until: float = -1.0
    generator_off_until: float = -1.0
    elevator_open_until: float = -1.0
    elevator: Rect | None = None
    lever: tuple = (0.0, 0.0)
    sugar: dict | None = None

    def __post_init__(self):
        c = self.cfg
        self.bounds = tuple(float(v) for v in c["bounds"])
        self.walls = [Rect(*map(float, w)) for w in c["walls"]]
        d = c["secrets"]["s2_corredor"]["door"]
        self.door_s2 = Rect(float(d["x"]), float(d["y"]), float(d["w"]), float(d["h"]))
        z = c["secrets"]["s4_elevador"]["zone"]
        self.elevator = Rect(float(z["x"]), float(z["y"]), float(z["w"]), float(z["h"]))
        self.lever = tuple(map(float, c["secrets"]["s3_alavanca"]["lever"]))
        self.sugar = c.get("sugar_patch")

    # ---- estados dos mecanismos ----
    def door_open(self, t: float) -> bool:
        return t < self.door_open_until

    def hatch_open(self, t: float) -> bool:
        return t < self.hatch_open_until

    def generator_off(self, t: float) -> bool:
        return t < self.generator_off_until

    def elevator_open(self, t: float) -> bool:
        return t < self.elevator_open_until

    def obstacles(self, t: float) -> list[Rect]:
        obs = list(self.walls)
        if not self.door_open(t):
            obs.append(self.door_s2)
        return obs

    def entry(self, name: str) -> tuple[float, float]:
        x, y = self.cfg["entries"][name]
        return float(x), float(y)

    def in_elevator(self, x: float, y: float) -> bool:
        return self.elevator.contains(x, y)

    def state_row(self, t: float) -> list[float]:
        """[porta S2 aberta, escotilha aberta, gerador desligado, elevador aberto] para o replay."""
        return [float(self.door_open(t)), float(self.hatch_open(t)), float(self.generator_off(t)), float(self.elevator_open(t))]
