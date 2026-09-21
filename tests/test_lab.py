"""Laboratorio, robos, segredos e diario com cerebros-fantoche (so para exercitar a mecanica)."""

import math

import pytest

from interface.motor import MotorState
from replay.format import Replay
from world.diary import write_diary
from world.geometry import Terrain, Objects, load_world
from world.lab import Lab
from world.physics import Physics, FlyBody
from world.robots import RobotFleet
from world.secrets import Secrets
from world.simulation import Day


def setup():
    w = load_world()
    t = Terrain(w["arena"]["hills"], w["arena"]["radius_cm"])
    o = Objects.from_config(w)
    lab = Lab(w["lab"])
    ph = Physics(w, t, o, lab)
    return w, o, lab, ph


def test_ramp_leads_to_lab_and_lab_walls_block():
    w, o, lab, ph = setup()
    ramp = next(p for p in o.prisms if p.name == "prisma_co2")
    b = FlyBody("a", "female", ramp.x + 3.0, ramp.y, math.pi)   # olhando para a rampa
    for _ in range(400):
        ph.apply_motor(b, MotorState(forward_cm_s=2.0), 0.015)
        if b.level == "lab":
            break
    assert b.level == "lab" and (b.x, b.y) == lab.entry("rampa")
    # porta S2 fechada bloqueia a passagem para o leste
    b.x, b.y, b.heading = -2.0, 0.0, 0.0
    for _ in range(300):
        ph.apply_motor(b, MotorState(forward_cm_s=2.0), 0.015)
    assert b.x < lab.door_s2.x and "porta_s2" in b.contacts
    lab.door_open_until = 1e9
    for _ in range(300):
        ph.apply_motor(b, MotorState(forward_cm_s=2.0), 0.015)
    assert b.x > lab.door_s2.x            # porta aberta: passou


def test_hatch_requires_s1_and_lake_sinks():
    w, o, lab, ph = setup()
    cube = next(c for c in o.cubes if c.hollow)
    b = FlyBody("a", "female", cube.x - cube.half - 1.0, cube.y, 0.0)
    for _ in range(100):
        ph.apply_motor(b, MotorState(forward_cm_s=2.0), 0.015)
    assert b.level == "surface" and cube.name in b.contacts   # escotilha fechada: so encosta
    lab.hatch_open_until = 1e9
    ph.apply_motor(b, MotorState(forward_cm_s=2.0), 0.015)
    assert b.level == "lab" and (b.x, b.y) == lab.entry("escotilha")
    lake = o.water[0]
    c = FlyBody("c", "male", lake.x - lake.r - 0.5, lake.y, 0.0)
    ph.t = 0.0
    for k in range(1200):
        ph.t = k * 0.015
        ph.apply_motor(c, MotorState(forward_cm_s=2.0), 0.015)
        if c.level == "lab":
            break
    assert c.level == "lab" and (c.x, c.y) == lab.entry("lago")


def test_robot_patrols_chases_and_captures():
    w, o, lab, ph = setup()
    fleet = RobotFleet(w)
    r1 = fleet.robots[0]
    b = FlyBody("a", "female", r1.x + 2.0, r1.y, 0.0, level="lab")
    events = []
    for k in range(400):
        events += fleet.step([b], k * 0.015, 0.015, 1.0, False, lab, tuple(w["lab"]["exit_surface"]))
        if b.state == "capturada":
            break
    kinds = [e["kind"] for e in events]
    assert "robo_persegue" in kinds and "captura" in kinds and b.state == "capturada"
    for k in range(3000):
        events += fleet.step([b], 6 + k * 0.015, 0.015, 1.0, False, lab, tuple(w["lab"]["exit_surface"]))
        if b.level == "surface":
            break
    assert b.level == "surface" and b.state != "capturada" and any(e["kind"] == "soltura" for e in events)
    # gerador desligado congela; robo noturno so sai com luz baixa
    r1.state = "patrulha"
    ev = fleet.step([], 100.0, 0.015, 1.0, True, lab, (0, 0))
    assert r1.state == "congelado" and any(e["kind"] == "robo_congelado" for e in ev)
    r3 = next(r for r in fleet.robots if r.night_only)
    assert not r3.active
    fleet.step([], 101.0, 0.015, 0.1, False, lab, (0, 0))
    assert r3.active and r3.state == "patrulha"


def test_secrets_fire_and_near():
    w, o, lab, ph = setup()
    fleet = RobotFleet(w)
    sec = Secrets(w, lab, o)
    p1, p2 = sec.p1, sec.p2
    a = FlyBody("a", "female", p1.x, p1.y, 0.0, state="comendo")
    b = FlyBody("b", "male", p2.x + 1.5, p2.y, 0.0, state="andando")
    ev = sec.check([a, b], fleet, {}, 1.0)
    assert any(e["kind"] == "segredo_quase" and e["secret"] == "S1" for e in ev)
    b.x, b.state = p2.x, "comendo"
    ev = sec.check([a, b], fleet, {}, 2.0)
    assert any(e["kind"] == "segredo_disparado" and e["secret"] == "S1" for e in ev) and lab.hatch_open(3.0)
    # S2: macho cantando a < 2,5 cm da porta com femea do outro lado
    d = lab.door_s2
    m = FlyBody("m", "male", d.x - 1.0, d.y, 0.0, level="lab")
    f = FlyBody("f", "female", d.x + 2.0, d.y, 0.0, level="lab")
    ev = sec.check([m, f], fleet, {"m": False}, 10.0)
    assert any(e["secret"] == "S2" and e["kind"] == "segredo_quase" for e in ev)
    ev = sec.check([m, f], fleet, {"m": True}, 11.0)
    assert any(e["secret"] == "S2" and e["kind"] == "segredo_disparado" for e in ev) and lab.door_open(12.0)
    # S3: salto na alavanca com robo perseguindo -> gerador off e elevador aberto
    lx, ly = lab.lever
    j = FlyBody("j", "female", lx + 0.3, ly, 0.0, level="lab", state="saltando")
    fleet.robots[0].state, fleet.robots[0].target = "persegue", "j"
    ev = sec.check([j], fleet, {}, 20.0)
    assert any(e["secret"] == "S3" and e["kind"] == "segredo_disparado" for e in ev)
    assert lab.generator_off(21.0) and lab.elevator_open(21.0)
    # S4: 3 moscas no elevador aberto -> fuga
    z = lab.elevator
    trio = [FlyBody(n, "female", z.x, z.y, 0.0, level="lab") for n in ("x", "y", "w")]
    ev = sec.check(trio, fleet, {}, 22.0)
    assert any(e["kind"] == "fuga" for e in ev) and sec.escaped == {"x", "y", "w"} and all(t.level == "fora" for t in trio)
    s = sec.summary()
    assert s["S1"]["disparou"] == 1 and s["S1"]["quase"] == 1 and s["S4"]["disparou"] == 1


def test_diary_text():
    txt = write_diary(3, 60, [{"name": "Ada", "sex": "female", "hud": "k=3"}], {"Ada": {"distancia_cm": 12.0, "tempo_comendo_s": 4.0}},
                      [{"t": 1.0, "kind": "salto", "flies": ["Ada"]}, {"t": 5.0, "kind": "captura", "flies": ["Ada"], "robot": "R1"}],
                      {"S1": {"quase": 2, "disparou": 0, "eventos": [{"t": 1, "kind": "near", "flies": ["Ada", "Bia"]}]}, "fugiram": []})
    assert "Dia 3" in txt and "andou 12 cm" in txt and "comeu por 4 s" in txt and "R1 capturou Ada" in txt and "chegou perto 2×" in txt


class Puppet:
    def __init__(self, motor):
        self.motor = motor; self.ignited = False; self.last_window_spikes = 0; self.hud_label = "fantoche"
    def step(self, state):
        return self.motor


def test_day_records_lab_and_robots(tmp_path):
    day = Day(1.0, out_dir=tmp_path / "d", fly_factory=lambda ident: Puppet(MotorState(forward_cm_s=1.0)), log=lambda *a, **k: None)
    d = day.run()
    rp = Replay(d)
    assert rp.manifest["n_robots"] == 3 and rp.world.shape == (rp.manifest["ticks"], 3 * 4 + 4)
    assert "level" in rp.fi and (d / "diario.md").exists() and "Dia 0" in rp.manifest["diary"]
    assert "segredos" in day.stats["_dia"]
