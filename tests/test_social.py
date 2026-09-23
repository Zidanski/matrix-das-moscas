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


class _FakeRemote:
    """Cerebro remoto de mentira: responde pelo Pipe depois de `delay` s (para o modo tempo real)."""

    def __init__(self, delay: float):
        import multiprocessing as mp
        import threading
        self.conn, child = mp.Pipe()
        import numpy as np
        self.info = {"ok": True, "hud": "fake", "n": 0, "missing": [], "soma": np.zeros((0, 3), np.float32), "classes": np.zeros(0, np.uint8), "class_names": []}
        self.delay = delay
        self.n = 0

        def serve():
            import time as _t
            from dataclasses import asdict
            while True:
                msg = child.recv()
                if msg is None:
                    break
                if isinstance(msg, dict):
                    child.send({"ok": True, "cmd": msg.get("cmd")}); continue
                _t.sleep(self.delay); self.n += 1
                child.send({"motor": asdict(MotorState(forward_cm_s=0.5)), "ignited": False, "spikes": 0, "fired": []})
        threading.Thread(target=serve, daemon=True).start()

    def send(self, state, hunger): self.conn.send((state, hunger))
    def recv(self): return self.conn.recv()
    def command(self, cmd): self.conn.send({"cmd": cmd}); return self.conn.recv()
    def close(self):
        try: self.conn.send(None)
        except Exception: pass


def test_realtime_day_keeps_wall_clock_and_marks_skipped_windows(tmp_path):
    import time
    day = Day(1.5, out_dir=tmp_path / "rt", log=lambda *a, **k: None, realtime=True)
    fakes = [_FakeRemote(0.06 if i < 3 else 0.005) for i in range(6)]   # 3 cerebros lentos (60 ms por janela de 15 ms)
    day._spawn_brains = lambda: fakes
    t0 = time.time(); d = day.run(); wall = time.time() - t0
    assert 1.3 <= wall <= 4.0, f"tempo real: 1,5 s bio deveria levar ~1,5 s de parede, levou {wall:.1f}"
    rp = Replay(d)
    assert "brain_step" in rp.fi
    frac_slow = rp.col("brain_step")[:, 0].mean(); frac_fast = rp.col("brain_step")[:, 5].mean()
    assert frac_slow < 0.5 and frac_fast > frac_slow    # o lento pulou janelas; o rapido pegou mais (4 vagas para 6)
    assert rp.col("v")[:, 0].max() > 0.3                # motor mantido enquanto o cerebro calcula: a mosca anda
    assert day.stats["_dia"]["tempo_real"] is True and 0.3 < day.stats["_dia"]["ritmo_parede"] <= 1.2
    assert day.stats["Ada"]["fracao_de_ticks_com_cerebro"] < 0.5
    # comando de cerebro com o cerebro ocupado entra na fila e nao corrompe o pipe
    day2 = Day(0.6, out_dir=tmp_path / "rt2", log=lambda *a, **k: None, realtime=True)
    fakes2 = [_FakeRemote(0.2) for _ in range(6)]
    day2._spawn_brains = lambda: fakes2
    day2.flies = fakes2
    day2.commands = __import__("queue").Queue()
    day2.commands.put({"cmd": "reset_brain", "fly": "Ada"})
    d2 = day2.run()
    assert Replay(d2).manifest["realtime"] is True
