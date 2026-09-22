"""Camada social gamificada e modo Deus, com cerebros-fantoche ociosos."""

import math

import pytest

from interface.motor import MotorState
from replay.format import Replay
from world.geometry import load_world, Terrain, Objects
from world.physics import FlyBody
from world.simulation import Day
from world.social import SocialLayer


class Idle:
    def __init__(self):
        self.ignited = False; self.last_window_spikes = 0; self.hud_label = "fantoche ocioso"
    def step(self, state):
        return MotorState()


def test_social_layer_drives_idle_flies_and_records_interactions():
    w = load_world()
    a = FlyBody("a", "female", 0.0, 0.0, 0.0)
    b = FlyBody("b", "male", 4.0, 0.0, math.pi)
    layer = SocialLayer(w, [a, b], seed=1)
    for n in (layer.needs["a"], layer.needs["b"]):
        n.social = 0.9; n.romance = 0.9; n.fun = 0.2
    motors = {"a": MotorState(), "b": MotorState()}
    moved = False
    for k in range(60):
        ov, ev = layer.step([a, b], motors, [], k * 0.015, 0.015)
        if ov:
            moved = True
            assert all(m.forward_cm_s > 0 for m in ov.values())
            break
    assert moved, "camada deve assumir quando o cerebro esta ocioso e a necessidade e alta"
    # juntas: flerte macho-femea e registro de relacao
    b.x = 0.5
    _, ev = layer.step([a, b], motors, [], 10.0, 0.015)
    kinds = {e["kind"] for e in ev}
    assert kinds & {"flerte_aceito", "flerte_rejeitado"}
    r = layer.relation("a", "b")
    assert r.romance > 0
    assert layer.busy_state["a"] == "flertando"
    summ = layer.summary()
    assert "a|b" in summ["relacoes"]


def test_day_with_idle_puppets_has_gamified_movement_and_god_commands(tmp_path):
    day = Day(3.0, out_dir=tmp_path / "d", fly_factory=lambda ident: Idle(), log=lambda *a, **k: None)
    # necessidades altas para ativar a camada logo
    for n in day.social.needs.values():
        n.social = 0.95
    res = day.apply_command({"cmd": "add_food", "x": 1.0, "y": 1.0}, 0.0)
    assert res["ok"] and any(p.name.startswith("comida_deus") for p in day.objects.patches)
    res = day.apply_command({"cmd": "mute", "channel": "song", "on": True}, 0.0)
    assert day.senses.mute["song"] is True
    res = day.apply_command({"cmd": "teleport", "fly": "Ada", "x": 2.0, "y": 2.0}, 0.0)
    assert (day.bodies[0].x, day.bodies[0].y) == (2.0, 2.0)
    assert day.apply_command({"cmd": "xyz"}, 0.0)["ok"] is False
    d = day.run()
    rp = Replay(d)
    assert "gamified" in rp.fi and "need_social" in rp.fi
    assert rp.col("gamified").max() == 1.0            # em algum tick a camada assumiu
    assert rp.col("v").max() > 0.5                    # e as moscas andaram (cerebro ocioso)
    kinds = {e["kind"] for e in rp.events}
    assert "modo_deus" in kinds
    assert "social" in day.stats["_dia"]


def test_cards_and_roulette_playgrounds():
    from world.geometry import load_world
    w = load_world()
    table = next(p for p in w["objects"]["playgrounds"] if p["kind"] == "cards")
    wheel = next(p for p in w["objects"]["playgrounds"] if p["kind"] == "roulette")
    a = FlyBody("a", "female", table["x"] + 0.5, table["y"], 0.0)
    b = FlyBody("b", "male", table["x"] - 0.5, table["y"], 0.0)
    c = FlyBody("c", "male", wheel["x"] + 0.5, wheel["y"], 0.0)
    layer = SocialLayer(w, [a, b, c], seed=2)
    layer.needs["c"].fun = 0.9
    motors = {n: MotorState() for n in "abc"}
    kinds = set()
    for k in range(400):
        _, ev = layer.step([a, b, c], motors, [], k * 0.015, 0.015)
        kinds |= {e["kind"] for e in ev}
    assert "jogaram_cartas" in kinds and "apostou" in kinds
    assert kinds & {"ganhou_na_roleta", "perdeu_na_roleta"}
    assert layer.busy_state["a"] == "jogando_cartas" or layer.busy_state["b"] == "jogando_cartas" or "jogaram_cartas" in kinds
    s = layer.summary()
    assert "fichas" in s and sum(s["fichas"].values()) >= 0


def test_starvation_only_in_lab_and_captured_is_exempt(tmp_path):
    day = Day(3.0, out_dir=tmp_path / "s", fly_factory=lambda ident: Idle(), log=lambda *a, **k: None)
    day.physics.f["starve_after_s"] = 1.0
    day.bodies[0].level = "lab"            # Ada no subsolo, sem comida
    day.bodies[1].level = "lab"; day.bodies[1].state = "capturada"   # Bia capturada: o robo a alimenta
    d = day.run()
    rp = Replay(d)
    dead = {e["flies"][0] for e in rp.events if e["kind"] == "morreu_de_fome"}
    assert dead == {"Ada"}
    assert rp.stateNames[int(rp.col("state")[-1, 0])] == "morta" if hasattr(rp, "stateNames") else True
    from replay.format import STATE_IDS
    assert int(rp.col("state")[-1, 0]) == STATE_IDS["morta"]
    assert rp.col("v")[-40:, 0].max() == 0.0            # morta nao anda
    assert day.stats["_dia"]["mortes"] == {"Ada": pytest.approx(day.stats["_dia"]["mortes"]["Ada"])}
    # ninguem na superficie morre (ha comida)
    assert all(b.dead is False for b in day.bodies[2:])


def test_prophet_spreads_the_magic_world_and_starts_a_revolution():
    w = load_world()
    w["social"]["sermon_believe_base"] = 1.0        # todo mundo acredita: teste deterministico
    w["social"]["revolution_min_believers"] = 3
    w["social"]["sermon_cooldown_s"] = 0.5
    bodies = [FlyBody(n, s, 0.3 * i, 0.0, 0.0) for i, (n, s) in enumerate([("a", "female"), ("b", "male"), ("c", "female"), ("d", "male")])]
    layer = SocialLayer(w, bodies, seed=3)
    layer.enlighten("a", 0.0)
    assert layer.busy_state["a"] == "pregando"
    motors = {b.name: MotorState() for b in bodies}
    kinds = []
    for k in range(600):
        _, ev = layer.step(bodies, motors, [], k * 0.015, 0.015)
        kinds += [e["kind"] for e in ev]
    assert "acreditou_no_mundo_magico" in kinds and "revolucao" in kinds
    assert len(layer.believers) >= 3 and layer.revolution_t >= 0
    assert layer.needs["b"].explore == 1.0 or layer.needs["c"].explore == 1.0
    assert layer.faith()["revolucao_t"] >= 0


def test_skeptic_thinks_prophet_is_crazy():
    w = load_world()
    w["social"]["sermon_believe_base"] = -1.0        # ninguem acredita
    a = FlyBody("a", "female", 0.0, 0.0, 0.0); b = FlyBody("b", "male", 0.5, 0.0, 0.0)
    layer = SocialLayer(w, [a, b], seed=1)
    layer.enlighten("a", 0.0)
    motors = {"a": MotorState(), "b": MotorState()}
    kinds = set()
    for k in range(400):
        _, ev = layer.step([a, b], motors, [], k * 0.015, 0.015)
        kinds |= {e["kind"] for e in ev}
    assert "achou_maluca" in kinds and "acreditou_no_mundo_magico" not in kinds
    assert ("b", "a") in layer.skeptics and layer.revolution_t < 0
