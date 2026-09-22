"""Camada SOCIAL GAMIFICADA (estilo The Sims). NAO vem do cerebro.

Cada mosca tem necessidades (social, diversao, romance) que sobem com o tempo.
Quando o cerebro NAO manda nada (parada, sem comer/saltar/recuar), a camada
escolhe o desejo mais forte e conduz a mosca ate o alvo: outra mosca (social),
uma bola (diversao) ou um par do sexo oposto (romance). Interacoes por
proximidade geram eventos e relacoes por par:
  comeram_juntas  duas comendo a < 2 cm         amizade +
  dancaram        duas a < 1 cm, ambas querendo  amizade +, diversao -
  jogaram_bola    empurrou a bola ate outra      amizade +, diversao -
  flerte          macho romantico junto da femea -> aceito (romance ++) ou rejeitado
Tudo isso e PREMISSA de jogo; o replay marca cada tick como 'reflexo' (0) ou
'gamificado' (1) e o README declara a camada.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from interface.motor import MotorState
from .geometry import bearing, wrap_angle


@dataclass
class Needs:
    social: float = 0.3
    fun: float = 0.3
    romance: float = 0.2
    explore: float = 0.1


@dataclass
class Relation:
    amizade: float = 0.0
    romance: float = 0.0


class _Pt:
    """Alvo pontual (mesa, roleta, rampa, porta, elevador)."""

    def __init__(self, x, y, level):
        self.x, self.y, self.level = float(x), float(y), level


class SocialLayer:
    def __init__(self, cfg: dict, bodies: list, seed: int = 0):
        c = cfg.get("social", {})
        self.enabled = bool(c.get("enabled", True))
        self.rise = {"social": float(c.get("social_rise_per_s", 0.012)), "fun": float(c.get("fun_rise_per_s", 0.010)),
                     "romance_m": float(c.get("romance_rise_male_per_s", 0.012)), "romance_f": float(c.get("romance_rise_female_per_s", 0.006)),
                     "explore": float(c.get("explore_rise_per_s", 0.0))}
        self.accept_base = float(c.get("flirt_accept_base", 0.4))
        self.cd = {"flirt": float(c.get("cooldown_flirt_s", 12)), "dance": float(c.get("cooldown_dance_s", 20)), "meet": float(c.get("cooldown_meet_s", 10))}
        self.lab = cfg.get("lab", {})
        self.ramp = next((pr for pr in cfg["objects"]["prisms"] if pr["name"] == "prisma_co2"), None)
        self.threshold = float(c.get("wish_threshold", 0.6))
        self.idle_ticks = int(c.get("idle_ticks_before_wish", 20))
        self.speed = float(c.get("walk_cm_s", 1.0))
        self.turn_gain = float(c.get("turn_gain", 2.0))
        self.needs = {b.name: Needs() for b in bodies}
        self.rel: dict[tuple[str, str], Relation] = {}
        self.idle = {b.name: 0 for b in bodies}
        self.busy_until = {b.name: -1.0 for b in bodies}     # dancando/flertando
        self.busy_state = {b.name: "" for b in bodies}
        self.cool: dict[str, float] = {}
        self.ball_kick: dict[str, tuple[str, float]] = {}    # bola -> (quem chutou, t)
        self.rng = random.Random(seed)
        self.chips = {b.name: int(c.get("chips_start", 10)) for b in bodies}
        self.win_prob = float(c.get("roulette_win_prob", 0.35))
        self.cards_s = float(c.get("cards_rounds_s", 4.0))
        self.spin_s = float(c.get("roulette_spin_s", 3.0))
        self.playgrounds = [pg for pg in getattr(cfg, "get", lambda k, d=None: d)("objects", {}).get("playgrounds", [])]
        # cada mosca tem um passatempo favorito (semente): bola, cartas ou roleta
        kinds = ["ball", "cards", "roulette"]
        self.favorite = {b.name: kinds[(hash(b.name) + seed) % 3] for b in bodies}
        self.pending_spin: dict[str, tuple[float, int]] = {}   # mosca -> (t do resultado, aposta)
        # o mundo magico: quem o robo devolve volta "iluminada" e conta; quem ouve acredita ou a acha maluca
        self.believe_base = float(c.get("sermon_believe_base", 0.35))
        self.sermon_cd = float(c.get("sermon_cooldown_s", 10))
        self.rev_min = int(c.get("revolution_min_believers", 3))
        self.prophets: set[str] = set()        # contam a historia
        self.believers: set[str] = set()       # acreditam (e passam a contar tambem)
        self.skeptics: set[tuple[str, str]] = set()   # (quem ouviu, quem contou): "acha maluca"
        self.revolution_t: float = -1.0

    def enlighten(self, name: str, t: float) -> None:
        """A mosca devolvida pelo robo viu o 'mundo magico': volta pregando."""
        self.prophets.add(name); self.believers.add(name)
        self.busy_until[name] = t + 4.0
        self.busy_state[name] = "pregando"

    def relation(self, a: str, b: str) -> Relation:
        key = (a, b) if a < b else (b, a)
        return self.rel.setdefault(key, Relation())

    def _cool(self, key: str, t: float, s: float) -> bool:
        if t - self.cool.get(key, -1e9) < s:
            return False
        self.cool[key] = t
        return True

    # ------------------------------------------------------------------ passo
    def step(self, bodies: list, motors: dict, spheres: list, t: float, dt: float) -> tuple[dict, list[dict]]:
        """Devolve (overrides {nome: MotorState}, eventos). Chamado apos o cerebro, antes da fisica."""
        overrides: dict = {}
        events: list[dict] = []
        if not self.enabled:
            return overrides, events
        alive = [b for b in bodies if b.level in ("surface", "lab") and b.state != "capturada" and not b.stuck and not getattr(b, "dead", False)]
        # necessidades sobem
        for b in alive:
            n = self.needs[b.name]
            n.social = min(1.0, n.social + self.rise["social"] * dt)
            n.fun = min(1.0, n.fun + self.rise["fun"] * dt)
            n.romance = min(1.0, n.romance + (self.rise["romance_m"] if b.sex == "male" else self.rise["romance_f"]) * dt)
            n.explore = min(1.0, n.explore + self.rise["explore"] * dt)
        # relacoes decaem devagar
        for r in self.rel.values():
            r.amizade = max(0.0, r.amizade - 0.0005 * dt)
            r.romance = max(0.0, r.romance - 0.0005 * dt)
        # ocupadas (dancando/flertando): ficam paradas no estado
        for b in alive:
            if t < self.busy_until[b.name]:
                overrides[b.name] = MotorState()
                b.state_override = self.busy_state[b.name]
            else:
                b.state_override = ""
        # desejos: so quando o cerebro esta ocioso
        for b in alive:
            if b.name in overrides:
                continue
            m: MotorState = motors[b.name]
            idle = abs(m.forward_cm_s) < 0.1 and m.backward_cm_s == 0 and not (m.feed and b.on_surface in ("sugar", "water")) and not m.jump
            self.idle[b.name] = self.idle[b.name] + 1 if idle else 0
            if self.idle[b.name] < self.idle_ticks:
                continue
            n = self.needs[b.name]
            wish, val = max((("social", n.social), ("fun", n.fun), ("romance", n.romance), ("explore", n.explore)), key=lambda kv: kv[1])
            if self.revolution_t >= 0 and b.name in self.believers:
                wish, val = "explore", 1.0          # revolucao: as crentes marcham para o laboratorio
                n.explore = 1.0
            if val < self.threshold:
                continue
            target = None
            if wish == "social":
                others = [o for o in alive if o is not b]
                target = min(others, key=lambda o: math.hypot(o.x - b.x, o.y - b.y), default=None)
            elif wish == "fun":
                if b.level != "surface":
                    continue
                fav = self.favorite[b.name]
                cands = []
                for s_ in spheres:
                    cands.append((("ball", s_), math.hypot(s_.x - b.x, s_.y - b.y) * (0.5 if fav == "ball" else 1.0)))
                for pg in self.playgrounds:
                    kind = "cards" if pg["kind"] == "cards" else "roulette"
                    cands.append(((kind, _Pt(pg["x"], pg["y"], "surface")), math.hypot(pg["x"] - b.x, pg["y"] - b.y) * (0.5 if fav == kind else 1.0)))
                if not cands:
                    continue
                (kind, target), _ = min(cands, key=lambda kv: kv[1])
                b.wish = kind
            elif wish == "romance":
                others = [o for o in alive if o is not b and o.sex != b.sex and o.level == b.level]
                target = min(others, key=lambda o: math.hypot(o.x - b.x, o.y - b.y), default=None)
            else:  # explore: na superficie, a rampa; no laboratorio, a porta S2 e depois o elevador
                target = self._explore_target(b)
            if target is None or getattr(target, "level", b.level) != b.level:
                continue
            d = math.hypot(target.x - b.x, target.y - b.y)
            if wish == "explore" and d < 1.2:
                n.explore = 0.0
            reach = 1.4 if wish == "fun" and getattr(b, "wish", "") in ("cards", "roulette") else 0.9
            if d > reach:
                br = bearing(b.x, b.y, b.heading, target.x, target.y)
                overrides[b.name] = MotorState(forward_cm_s=self.speed if abs(br) < 1.2 else 0.3,
                                               turn_rad_s=max(-3.0, min(3.0, self.turn_gain * br)))
                b.wish = wish
        # ---------------------------------------------------- interacoes por proximidade
        for i, a in enumerate(alive):
            for o in alive[i + 1:]:
                if a.level != o.level:
                    continue
                d = math.hypot(a.x - o.x, a.y - o.y)
                if d > 2.0:
                    continue
                pair = f"{a.name}|{o.name}"
                # sermao do mundo magico: profeta perto de quem ainda nao acredita
                if d < 1.5 and (a.name in self.prophets) != (o.name in self.prophets) and t >= self.busy_until[a.name] and t >= self.busy_until[o.name]:
                    prophet, listener = (a, o) if a.name in self.prophets else (o, a)
                    if listener.name not in self.believers and self._cool("sermon" + pair, t, self.sermon_cd):
                        r = self.relation(prophet.name, listener.name)
                        p = self.believe_base + 0.4 * r.amizade + 0.3 * r.romance
                        believed = self.rng.random() < p
                        self.busy_until[prophet.name] = t + 3.0; self.busy_state[prophet.name] = "pregando"
                        self.busy_until[listener.name] = t + 3.0; self.busy_state[listener.name] = "ouvindo"
                        if believed:
                            self.believers.add(listener.name); self.prophets.add(listener.name)
                            self._friend(prophet, listener, 0.2)
                            events.append({"kind": "acreditou_no_mundo_magico", "flies": [prophet.name, listener.name], "chance": round(p, 2)})
                            if len(self.believers) >= self.rev_min and self.revolution_t < 0:
                                self.revolution_t = t
                                for nm in self.believers:
                                    self.needs[nm].explore = 1.0
                                events.append({"kind": "revolucao", "flies": sorted(self.believers)})
                        else:
                            r.amizade = max(0.0, r.amizade - 0.1)
                            self.skeptics.add((listener.name, prophet.name))
                            events.append({"kind": "achou_maluca", "flies": [listener.name, prophet.name], "chance": round(p, 2)})
                        continue
                if a.state == "comendo" and o.state == "comendo" and self._cool("eat" + pair, t, 15):
                    self._friend(a, o, 0.15); self.needs[a.name].social -= 0.3; self.needs[o.name].social -= 0.3
                    events.append({"kind": "comeram_juntas", "flies": [a.name, o.name]})
                if d < 1.0 and t >= self.busy_until[a.name] and t >= self.busy_until[o.name]:
                    na, no = self.needs[a.name], self.needs[o.name]
                    if a.sex != o.sex and (na.romance > 0.5 or no.romance > 0.5) and self._cool("flirt" + pair, t, self.cd["flirt"]):
                        male, fem = (a, o) if a.sex == "male" else (o, a)
                        r = self.relation(a.name, o.name)
                        nf = self.needs[fem.name]
                        accept = nf.romance > 0.3 and self.rng.random() < self.accept_base + 0.5 * r.amizade
                        r.romance = min(1.0, r.romance + (0.3 if accept else 0.08))
                        self.needs[male.name].romance = max(0.0, self.needs[male.name].romance - (0.5 if accept else 0.2))
                        if accept:
                            nf.romance = max(0.0, nf.romance - 0.4)
                        for x in (a, o):
                            self.busy_until[x.name] = t + 2.5
                            self.busy_state[x.name] = "flertando"
                        events.append({"kind": "flerte_aceito" if accept else "flerte_rejeitado", "flies": [male.name, fem.name]})
                    elif na.fun > 0.5 and no.fun > 0.5 and self._cool("dance" + pair, t, self.cd["dance"]):
                        self._friend(a, o, 0.2); na.fun -= 0.4; no.fun -= 0.4; na.social -= 0.2; no.social -= 0.2
                        for x in (a, o):
                            self.busy_until[x.name] = t + 3.0
                            self.busy_state[x.name] = "dancando"
                        events.append({"kind": "dancaram", "flies": [a.name, o.name]})
                    elif self._cool("meet" + pair, t, self.cd["meet"]):
                        self._friend(a, o, 0.05); na.social -= 0.15; no.social -= 0.15
        # bola: quem chutou e quem recebeu (chute vira animacao de 0,6 s)
        for s in spheres:
            if abs(s.vx) + abs(s.vy) > 0.05:
                kicker = next((b for b in alive if s.name in b.contacts), None)
                if kicker:
                    if self.ball_kick.get(s.name, ("", -1e9))[1] < t - 1.0:
                        self.busy_until[kicker.name] = t + 0.6
                        self.busy_state[kicker.name] = "jogando_bola"
                    self.ball_kick[s.name] = (kicker.name, t)
                    self.needs[kicker.name].fun = max(0.0, self.needs[kicker.name].fun - 0.15)
            k = self.ball_kick.get(s.name)
            if k and t - k[1] < 6.0:
                for b in alive:
                    if b.name != k[0] and b.level == "surface" and math.hypot(b.x - s.x, b.y - s.y) < s.r + 1.0 and self._cool("ball" + s.name, t, 8):
                        kicker_body = next((x for x in alive if x.name == k[0]), None)
                        if kicker_body:
                            self._friend(kicker_body, b, 0.15)
                        self.needs[b.name].fun = max(0.0, self.needs[b.name].fun - 0.3)
                        self.busy_until[b.name] = t + 0.6
                        self.busy_state[b.name] = "jogando_bola"
                        events.append({"kind": "jogaram_bola", "flies": [k[0], b.name], "objeto": s.name})
                        self.ball_kick.pop(s.name, None)
                        break
        # cartas: duas ou mais moscas na mesa -> partida; roleta: aposta de fichas
        for pg in self.playgrounds:
            at = [b for b in alive if b.level == "surface" and math.hypot(b.x - pg["x"], b.y - pg["y"]) < float(pg["r"]) + 0.6 and t >= self.busy_until[b.name]]
            if pg["kind"] == "cards" and len(at) >= 2 and self._cool("cards" + pg["name"], t, self.cards_s + 4):
                players = at[:4]
                winner = self.rng.choice(players)
                for x in players:
                    self.busy_until[x.name] = t + self.cards_s
                    self.busy_state[x.name] = "jogando_cartas"
                    self.needs[x.name].fun = max(0.0, self.needs[x.name].fun - 0.35)
                    self.needs[x.name].social = max(0.0, self.needs[x.name].social - 0.2)
                for i_, x in enumerate(players):
                    for y_ in players[i_ + 1:]:
                        self._friend(x, y_, 0.1)
                self.chips[winner.name] += len(players) - 1
                for x in players:
                    if x is not winner and self.chips[x.name] > 0:
                        self.chips[x.name] -= 1
                events.append({"kind": "jogaram_cartas", "flies": [x.name for x in players], "vencedor": winner.name})
            elif pg["kind"] == "roulette":
                for b in at:
                    if self.needs[b.name].fun < 0.3 or self.chips[b.name] <= 0 or not self._cool("bet" + b.name, t, self.spin_s + 3):
                        continue
                    bet = min(self.chips[b.name], self.rng.choice([1, 1, 2, 3]))
                    self.chips[b.name] -= bet
                    self.busy_until[b.name] = t + self.spin_s
                    self.busy_state[b.name] = "apostando"
                    self.pending_spin[b.name] = (t + self.spin_s, bet)
                    events.append({"kind": "apostou", "flies": [b.name], "fichas": bet})
        for name, (t_res, bet) in list(self.pending_spin.items()):
            if t >= t_res:
                won = self.rng.random() < self.win_prob
                if won:
                    self.chips[name] += 2 * bet
                    self.needs[name].fun = max(0.0, self.needs[name].fun - 0.5)
                    events.append({"kind": "ganhou_na_roleta", "flies": [name], "fichas": 2 * bet, "saldo": self.chips[name]})
                else:
                    self.needs[name].fun = max(0.0, self.needs[name].fun - 0.2)
                    events.append({"kind": "perdeu_na_roleta", "flies": [name], "fichas": bet, "saldo": self.chips[name]})
                self.pending_spin.pop(name)
        for b in alive:
            n = self.needs[b.name]
            n.social = max(0.0, n.social); n.fun = max(0.0, n.fun); n.romance = max(0.0, n.romance); n.explore = max(0.0, n.explore)
        return overrides, events

    def _explore_target(self, b):
        if b.level == "surface" and self.ramp is not None:
            return _Pt(float(self.ramp["x"]), float(self.ramp["y"]), "surface")
        if b.level == "lab" and self.lab:
            door = self.lab["secrets"]["s2_corredor"]["door"]
            zone = self.lab["secrets"]["s4_elevador"]["zone"]
            if b.x < float(door["x"]) - 0.5:       # oeste da porta: vai a porta; leste: vai ao elevador
                return _Pt(float(door["x"]) - 1.5, float(door["y"]), "lab")
            return _Pt(float(zone["x"]), float(zone["y"]), "lab")
        return None

    def _friend(self, a, b, amount: float):
        r = self.relation(a.name, b.name)
        r.amizade = min(1.0, r.amizade + amount)

    def rows(self, name: str) -> list[float]:
        n = self.needs.get(name, Needs())
        return [n.social, n.fun, n.romance]

    def faith(self) -> dict:
        return {"profetas": sorted(self.prophets), "crentes": sorted(self.believers),
                "ceticos": sorted(f"{a} acha {b} maluca" for a, b in self.skeptics), "revolucao_t": self.revolution_t}

    def summary(self) -> dict:
        return {"fe": self.faith(), "fichas": dict(self.chips), "favoritos": dict(self.favorite),
                "relacoes": {f"{a}|{b}": {"amizade": round(r.amizade, 3), "romance": round(r.romance, 3)} for (a, b), r in self.rel.items()},
                "necessidades": {k: {"social": round(v.social, 2), "fun": round(v.fun, 2), "romance": round(v.romance, 2)} for k, v in self.needs.items()}}
