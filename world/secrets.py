"""Os quatro segredos: mecanismos fisicos que exigem coincidencia de reflexos.

Cada segredo registra "quase" (near) e "disparou" (fired), com dia e moscas.
Nenhum segredo e impossivel para uma mosca sozinha; todos sao improvaveis.
  S1 placa dupla : duas moscas comendo ao mesmo tempo nas duas manchas de acucar
                   a 3 cm -> escotilha do cubo oco abre por hatch_open_s
  S2 corredor    : porta abre enquanto um macho canta a < sing_cm dela e uma
                   femea esta do outro lado a < female_cm
  S3 alavanca    : mosca em salto colide com a alavanca enquanto um robo a
                   persegue -> gerador desliga (robos congelam) por generator_off_s
                   e o elevador abre por open_after_s3_s
  S4 elevador    : min_flies moscas dentro do elevador aberto -> sobe: fuga
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class SecretLog:
    near: int = 0
    fired: int = 0
    events: list = field(default_factory=list)   # {t, kind: near|fired, flies}

    def hit(self, kind: str, t: float, flies: list[str], **d):
        if kind == "near":
            self.near += 1
        else:
            self.fired += 1
        self.events.append({"t": round(t, 2), "kind": kind, "flies": flies, **d})


class Secrets:
    def __init__(self, world_cfg: dict, lab, objects):
        self.c = world_cfg["lab"]["secrets"]
        self.lab = lab
        self.objects = objects
        self.log = {k: SecretLog() for k in ("S1", "S2", "S3", "S4")}
        self.escaped: set[str] = set()
        self._near_cool: dict[str, float] = {}
        p1n, p2n = self.c["s1_placa_dupla"]["patches"]
        self.p1 = next(p for p in objects.patches if p.name == p1n)
        self.p2 = next(p for p in objects.patches if p.name == p2n)

    def _near_once(self, key: str, t: float, cool: float = 5.0) -> bool:
        if t - self._near_cool.get(key, -1e9) < cool:
            return False
        self._near_cool[key] = t
        return True

    def check(self, bodies: list, robots, songs: dict, t: float) -> list[dict]:
        ev = []
        lab = self.lab
        # ---- S1: placa dupla ----
        c1 = self.c["s1_placa_dupla"]
        on1 = [b for b in bodies if b.level == "surface" and b.state == "comendo" and math.hypot(b.x - self.p1.x, b.y - self.p1.y) < self.p1.r + 0.3]
        on2 = [b for b in bodies if b.level == "surface" and b.state == "comendo" and math.hypot(b.x - self.p2.x, b.y - self.p2.y) < self.p2.r + 0.3]
        if on1 and on2 and not lab.hatch_open(t):
            lab.hatch_open_until = t + float(c1["hatch_open_s"])
            names = [on1[0].name, on2[0].name]
            self.log["S1"].hit("fired", t, names)
            ev.append({"kind": "segredo_disparado", "secret": "S1", "flies": names})
        elif (on1 or on2) and not lab.hatch_open(t):
            other = self.p2 if on1 else self.p1
            close = [b for b in bodies if b.level == "surface" and b.state != "comendo" and math.hypot(b.x - other.x, b.y - other.y) < float(c1["near_cm"])]
            if close and self._near_once("S1", t):
                names = [(on1 or on2)[0].name, close[0].name]
                self.log["S1"].hit("near", t, names)
                ev.append({"kind": "segredo_quase", "secret": "S1", "flies": names})
        # ---- S2: corredor de corte ----
        c2 = self.c["s2_corredor"]
        d = lab.door_s2
        males = [b for b in bodies if b.level == "lab" and b.sex == "male" and math.hypot(b.x - d.x, b.y - d.y) < float(c2["sing_cm"])]
        singing = [b for b in males if songs.get(b.name)]
        for m in males:
            fem = [f for f in bodies if f.level == "lab" and f.sex == "female" and math.hypot(f.x - d.x, f.y - d.y) < float(c2["female_cm"]) and (f.x - d.x) * (m.x - d.x) < 0]
            if m in singing and fem:
                if not lab.door_open(t):
                    lab.door_open_until = t + float(c2["open_s"])
                    self.log["S2"].hit("fired", t, [m.name, fem[0].name])
                    ev.append({"kind": "segredo_disparado", "secret": "S2", "flies": [m.name, fem[0].name]})
            elif (m in singing or fem) and self._near_once("S2", t):
                self.log["S2"].hit("near", t, [m.name] + [f.name for f in fem[:1]])
                ev.append({"kind": "segredo_quase", "secret": "S2", "flies": [m.name] + [f.name for f in fem[:1]]})
        # ---- S3: alavanca do gerador ----
        c3 = self.c["s3_alavanca"]
        lx, ly = lab.lever
        for b in bodies:
            if b.level != "lab":
                continue
            dl = math.hypot(b.x - lx, b.y - ly)
            if dl < float(c3["hit_cm"]) and b.state == "saltando":
                if robots.chasing(b.name):
                    if not lab.generator_off(t):
                        lab.generator_off_until = t + float(c3["generator_off_s"])
                        lab.elevator_open_until = t + float(self.c["s4_elevador"]["open_after_s3_s"])
                        self.log["S3"].hit("fired", t, [b.name])
                        ev.append({"kind": "segredo_disparado", "secret": "S3", "flies": [b.name]})
                elif self._near_once("S3", t):
                    self.log["S3"].hit("near", t, [b.name], motivo="salto na alavanca sem robo perseguindo")
                    ev.append({"kind": "segredo_quase", "secret": "S3", "flies": [b.name]})
            elif dl < float(c3["chase_cm"]) and robots.chasing(b.name) and self._near_once("S3b", t):
                self.log["S3"].hit("near", t, [b.name], motivo="perseguida perto da alavanca, sem salto")
                ev.append({"kind": "segredo_quase", "secret": "S3", "flies": [b.name]})
        # ---- S4: elevador ----
        c4 = self.c["s4_elevador"]
        inside = [b for b in bodies if b.level == "lab" and lab.in_elevator(b.x, b.y) and b.state != "capturada"]
        if inside:
            if lab.elevator_open(t) and len(inside) >= int(c4["min_flies"]):
                names = [b.name for b in inside]
                for b in inside:
                    b.level = "fora"; b.state = "parada"; b.v = 0.0
                    self.escaped.add(b.name)
                self.log["S4"].hit("fired", t, names)
                ev.append({"kind": "segredo_disparado", "secret": "S4", "flies": names})
                ev.append({"kind": "fuga", "flies": names})
            elif self._near_once("S4", t, cool=10.0):
                names = [b.name for b in inside]
                self.log["S4"].hit("near", t, names, aberto=lab.elevator_open(t))
                ev.append({"kind": "segredo_quase", "secret": "S4", "flies": names})
        return ev

    def summary(self) -> dict:
        return {k: {"quase": v.near, "disparou": v.fired, "eventos": v.events} for k, v in self.log.items()} | {"fugiram": sorted(self.escaped)}
