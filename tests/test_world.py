"""Testes do mundo com cerebros-fantoche (so para exercitar fisica, sensores e replay)."""

import math

import numpy as np
import pytest

from interface.motor import MotorState
from replay.format import Replay, STATE_IDS
from world.geometry import Terrain, Objects, load_world, bearing, sides_from_bearing
from world.physics import Physics, FlyBody
from world.senses import Senses
from world.simulation import Day


class Puppet:
    """Cerebro-fantoche: devolve sempre o mesmo MotorState (teste da fisica, nao do mundo real)."""

    def __init__(self, motor: MotorState):
        self.motor = motor
        self.ignited = False
        self.last_window_spikes = 0
        self.hud_label = "fantoche"

    def step(self, state):
        self.last_state = state
        return self.motor


def world_and_physics():
    w = load_world()
    t = Terrain(w["arena"]["hills"], w["arena"]["radius_cm"])
    o = Objects.from_config(w)
    return w, t, o, Physics(w, t, o)


def test_bearing_and_sides():
    assert bearing(0, 0, 0.0, 0, 1) == pytest.approx(math.pi / 2)     # alvo a esquerda
    l, r = sides_from_bearing(math.pi / 2)
    assert l == pytest.approx(1.0) and r == pytest.approx(0.0)
    l, r = sides_from_bearing(0.0)
    assert l == r == pytest.approx(0.5)


def test_forward_walk_and_wall():
    w, t, o, ph = world_and_physics()
    b = FlyBody("x", "female", 0.0, 0.0, 0.0)
    m = MotorState(forward_cm_s=1.0)
    for _ in range(100):
        ph.apply_motor(b, m, 0.015)
    assert b.x == pytest.approx(1.5, abs=1e-6) and b.state == "andando" and b.distance == pytest.approx(1.5, abs=1e-6)
    b = FlyBody("x", "female", w["arena"]["radius_cm"] - 0.5, 0.0, 0.0)
    ph.apply_motor(b, MotorState(forward_cm_s=2.0), 1.0)
    assert "parede" in b.contacts and math.hypot(b.x, b.y) <= w["arena"]["radius_cm"]


def test_cube_blocks_and_sphere_rolls():
    w, t, o, ph = world_and_physics()
    c = o.cubes[0]
    b = FlyBody("x", "female", c.x - c.half - 1.0, c.y, 0.0)
    for _ in range(200):
        ph.apply_motor(b, MotorState(forward_cm_s=2.0), 0.015)
    assert c.name in b.contacts and b.x < c.x - c.half
    s = o.spheres[0]
    b = FlyBody("y", "male", s.x - s.r - 1.0, s.y, 0.0)
    x0 = s.x
    for _ in range(100):
        ph.apply_motor(b, MotorState(forward_cm_s=2.0), 0.015)
        ph.step_objects(0.015)
    assert s.pushes > 0 and s.x > x0          # a esfera rolou para longe
    assert b.on_surface == "sugar"            # bola doce: superficie de acucar sob as pernas


def test_water_traps_until_touched():
    w, t, o, ph = world_and_physics()
    lake = o.water[0]
    b = FlyBody("a", "female", lake.x - lake.r - 0.5, lake.y, 0.0)
    for _ in range(300):
        ph.apply_motor(b, MotorState(forward_cm_s=2.0), 0.015)
    assert b.stuck and b.state == "presa" and b.on_surface == "water"
    x_stuck = b.x
    ph.apply_motor(b, MotorState(forward_cm_s=2.0), 0.015)
    assert b.x == x_stuck                     # presa: nao anda
    other = FlyBody("b", "male", b.x + 0.3, b.y, 0.0)
    freed = ph.rescue_check([b, other])
    assert freed == [("a", "b")] and not b.stuck


def test_feeding_and_hunger():
    w, t, o, ph = world_and_physics()
    p = o.patches[0]
    b = FlyBody("a", "female", p.x, p.y, 0.0)
    ph.apply_motor(b, MotorState(feed=True), 0.015)
    assert b.on_surface == "sugar" and b.state == "comendo"
    ph.update_hunger(b, 10.0, 0.015)
    assert b.hunger_gain == 1.0 and b.time_feeding > 0
    b2 = FlyBody("c", "male", 30.0, 30.0, 0.0)
    ph.update_hunger(b2, 20.0, 0.015)
    assert b2.hunger_gain == pytest.approx(min(2.0, 1.0 + 0.03 * 20.0))


def test_senses_odor_sides_and_social():
    w, t, o, ph = world_and_physics()
    s = Senses(w, o)
    food = next(p for p in o.prisms if p.odor == "food")
    # mosca olhando para +x com a comida a esquerda: antena esquerda mais perto -> orn_dm1 E > D
    b = FlyBody("a", "female", food.x, food.y - 3.0, 0.0)
    st = s.sense(b, [b], {}, 0.0, 0.015)
    l, r = st["orn_dm1"]
    assert l > r > 0
    # macho a 1 cm emite cVA; canta -> JO; contato ppk23 quando encosta
    m = FlyBody("m", "male", b.x, b.y - 0.4, 0.0)   # a direita de quem olha para +x
    st = s.sense(b, [b, m], {"m": True}, 0.0, 0.015)
    assert st["orn_da1"][0] > 0 and st["jo_a"][1] > st["jo_a"][0]   # macho a direita: canção mais forte a direita
    assert "ppk23" in st and "jo_ce" in st
    # looming: macho se aproximando entre dois ticks
    m.x = b.x + 3.0; s.sense(b, [b, m], {}, 0.0, 0.015)
    m.x = b.x + 2.0; st = s.sense(b, [b, m], {}, 0.015, 0.015)
    assert st["lc4"][1] > 0
    # noite: odor mais fraco
    assert s.light(0.0) == pytest.approx(1.0) and s.light(w["arena"]["day_length_s"] / 2) == pytest.approx(0.0)


def test_day_with_puppets_writes_replay(tmp_path):
    w = load_world()
    motors = {"Ada": MotorState(forward_cm_s=1.0, turn_rad_s=0.3), "Bia": MotorState(), "Cleo": MotorState(feed=True),
              "Dan": MotorState(forward_cm_s=0.5, song=True), "Edu": MotorState(backward_cm_s=0.5), "Fil": MotorState(jump=True)}
    day = Day(1.5, out_dir=tmp_path / "d", fly_factory=lambda ident: Puppet(motors[ident["name"]]), log=lambda *a, **k: None)
    d = day.run()
    rp = Replay(d)
    assert rp.manifest["ticks"] == 100 and rp.frames.shape == (100, 6, len(rp.fields))
    ada = rp.frames[:, 0, :]
    assert ada[-1, rp.fi["x"]] != ada[0, rp.fi["x"]]                 # Ada andou
    assert rp.col("state")[-1, 1] == STATE_IDS["parada"]             # Bia parada
    assert rp.col("song")[:, 3].max() == 1.0                          # Dan cantou
    assert rp.col("v")[:, 4].min() < 0                                # Edu deu re
    assert (rp.col("state")[:, 5] == STATE_IDS["saltando"]).any()    # Fil saltou
    kinds = {e["kind"] for e in rp.events}
    assert "estado" in kinds
    assert "Ada" in day.stats and day.stats["Ada"]["distancia_cm"] > 0
