"""Camada social gamificada e modo Deus, com cerebros-fantoche ociosos."""

import math

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
