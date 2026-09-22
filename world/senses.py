"""Situacao fisica -> SensoryState por mosca (valores [0,1] por lado, E/D).

Aqui esta a metade (a) da regra de ouro: o mundo transforma a situacao fisica
em estimulos. Nenhum valor depende de "intencao"; so de geometria e contato.
"""

from __future__ import annotations

import math

from .geometry import Objects, bearing, sides_from_bearing
from .physics import FlyBody


class Senses:
    def __init__(self, cfg: dict, objects: Objects):
        self.cfg = cfg
        self.s = cfg["senses"]
        self.f = cfg["fly"]
        self.objects = objects
        self.prev_theta: dict[tuple[str, str], float] = {}   # (mosca, alvo) -> tamanho angular anterior
        self.day = cfg["arena"]
        self.mute = {"song": False, "cva": False, "contact": False}   # modo Deus: "trocar a lingua"

    def light(self, t: float) -> float:
        T = float(self.day["day_length_s"])
        return 0.5 + 0.5 * math.cos(2 * math.pi * t / T)

    def _antennae(self, b: FlyBody) -> tuple[tuple[float, float], tuple[float, float]]:
        fw, lat = float(self.f["antenna_forward_cm"]), float(self.f["antenna_lateral_cm"])
        c, s = math.cos(b.heading), math.sin(b.heading)
        hx, hy = b.x + fw * c, b.y + fw * s
        return (hx - lat * s, hy + lat * c), (hx + lat * s, hy - lat * c)   # esquerda, direita

    @staticmethod
    def _gauss(px, py, sx, sy, strength, sigma) -> float:
        d2 = (px - sx) ** 2 + (py - sy) ** 2
        return strength * math.exp(-d2 / (2 * sigma * sigma))

    def sense(self, b: FlyBody, others: list, songs: dict[str, bool], t: float, dt: float, robots: list | None = None) -> dict:
        st: dict[str, tuple[float, float]] = {}
        if b.level == "fora":
            return st
        light = self.light(t)
        odor_scale = 1.0 - (1.0 - float(self.day["night_odor_scale"])) * (1.0 - light)
        loom_scale = 1.0 + (float(self.day["night_loom_scale"]) - 1.0) * (1.0 - light)
        (lx, ly), (rx, ry) = self._antennae(b)

        def add(name, l, r):
            l, r = min(1.0, max(0.0, l)), min(1.0, max(0.0, r))
            if l > 0 or r > 0:
                pl, pr = st.get(name, (0.0, 0.0))
                st[name] = (min(1.0, pl + l), min(1.0, pr + r))

        # gustacao por contato (labelo/pernas): superficie sob a mosca ou objeto encostado
        if b.on_surface in ("sugar", "bitter", "water"):
            add(b.on_surface, 1.0, 1.0)
            add("leg_grn", 0.6, 0.6)
        for name in b.contacts:
            if name != "agua_presa":
                add("leg_grn", 0.5, 0.5)
                add("jo_ce", 0.5, 0.5)     # antena/cabeca encosta em parede, cubo, esfera
        # odores das fontes (gaussianas), amostrados nas antenas E/D (so na superficie)
        for kind, sx, sy, strength, sigma in (self.objects.odor_sources() if b.level == "surface" else []):
            pop = {"food": "orn_dm1", "co2": "orn_v", "geosmin": "orn_da2"}[kind]
            add(pop, odor_scale * self._gauss(lx, ly, sx, sy, strength, sigma),
                odor_scale * self._gauss(rx, ry, sx, sy, strength, sigma))
        # outras moscas: cVA (machos), contato, cancao, objeto pequeno, looming
        cva_sigma, cva_str = float(self.s["cva_sigma_cm"]), float(self.s["cva_strength"])
        for o in list(others) + list(robots or []):
            if o is b or getattr(o, "level", "surface") != b.level:
                continue
            if getattr(o, "is_robot", False):
                if not o.active:
                    continue
                d = math.hypot(o.x - b.x, o.y - b.y)
                br = bearing(b.x, b.y, b.heading, o.x, o.y)
                sl, sr = sides_from_bearing(br, float(self.s["side_sharpness"]))
                if d < o.r + 2 * float(self.f["contact_radius_cm"]):
                    add("jo_ce", sl, sr); add("leg_grn", 0.5 * sl, 0.5 * sr)
                if abs(o.v) > float(self.s["small_object_min_speed_cm_s"]) and d < 2 * float(self.s["small_object_radius_cm"]):
                    a = 1.0 / (1.0 + d / 3.0)
                    add("lc11", a * sl, a * sr)
                self._loom(b, o.name, d, o.r, sl, sr, dt, loom_scale, add)
                continue
            d = math.hypot(o.x - b.x, o.y - b.y)
            br = bearing(b.x, b.y, b.heading, o.x, o.y)
            sl, sr = sides_from_bearing(br, float(self.s["side_sharpness"]))
            if o.sex == "male" and not self.mute["cva"]:
                cl = cva_str * self._gauss(lx, ly, o.x, o.y, 1.0, cva_sigma)
                cr = cva_str * self._gauss(rx, ry, o.x, o.y, 1.0, cva_sigma)
                add("orn_da1", cl, cr)
                add("orn_dl3", cl, cr)
            if d < 2 * float(self.f["contact_radius_cm"]) and not self.mute["contact"]:
                add("ppk23", sl, sr)          # so o macho tem a populacao; na femea e ignorado
                add("leg_grn", 0.5 * sl, 0.5 * sr)
                add("jo_ce", 0.5 * sl, 0.5 * sr)
            if songs.get(o.name) and d < float(self.s["song_radius_cm"]) and not self.mute["song"]:
                a = 1.0 / (1.0 + d)
                add("jo_a", a * sl, a * sr)
                add("jo_b", a * sl, a * sr)
            if d < float(self.s["small_object_radius_cm"]) and abs(o.v) > float(self.s["small_object_min_speed_cm_s"]):
                a = 1.0 / (1.0 + d / 2.0)
                add("lc11", a * sl, a * sr)
            self._loom(b, o.name, d, float(self.f["body_length_cm"]) / 2, sl, sr, dt, loom_scale, add)
        # looming de esferas em movimento
        for sph in self.objects.spheres:
            if abs(sph.vx) + abs(sph.vy) > 0.05:
                d = math.hypot(sph.x - b.x, sph.y - b.y)
                br = bearing(b.x, b.y, b.heading, sph.x, sph.y)
                sl, sr = sides_from_bearing(br)
                self._loom(b, sph.name, d, sph.r, sl, sr, dt, loom_scale, add)
        return st

    def _loom(self, b, key, d, r, sl, sr, dt, scale, add):
        theta = 2 * math.atan2(r, max(d, 1e-3))
        k = (b.name, key)
        prev = self.prev_theta.get(k, theta)
        self.prev_theta[k] = theta
        rate = (theta - prev) / max(dt, 1e-6)
        if rate > 0:
            v = min(1.0, rate / float(self.s["loom_gain"])) * scale
            add("lc4", v * sl, v * sr)
            add("lplc2", v * sl, v * sr)
