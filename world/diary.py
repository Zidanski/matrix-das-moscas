"""Diario automatico do dia: texto por regras a partir dos eventos e metricas. Sem LLM."""

from __future__ import annotations

from collections import Counter


def _fmt(n: float, dec: int = 1) -> str:
    return f"{n:.{dec}f}".replace(".", ",")


def write_diary(day_index: int, seconds: float, flies: list[dict], metrics: dict, events: list[dict], secrets: dict,
                interventions: list[dict] | None = None) -> str:
    L = []
    L.append(f"# Dia {day_index} — diário automático")
    L.append("")
    L.append(f"{_fmt(seconds, 0)} s biológicos, {len(flies)} moscas. Texto gerado por regras a partir dos eventos gravados; nada aqui foi roteirizado.")
    L.append("")
    sex = {f['name']: f['sex'] for f in flies}
    kinds = Counter(e["kind"] for e in events)
    # quem fez o que
    L.append("## As moscas")
    for f in flies:
        m = metrics.get(f["name"], {})
        bits = []
        if m.get("distancia_cm", 0) >= 5:
            bits.append(f"andou {_fmt(m['distancia_cm'], 0)} cm")
        elif m.get("distancia_cm", 0) > 0.5:
            bits.append(f"mal saiu do lugar ({_fmt(m['distancia_cm'])} cm)")
        else:
            bits.append("ficou parada o dia todo")
        if m.get("tempo_comendo_s", 0) >= 1:
            bits.append(f"comeu por {_fmt(m['tempo_comendo_s'], 0)} s")
        if m.get("ticks_convulsao", 0) > 0:
            bits.append("teve convulsão")
        if m.get("tempo_perto_de_outra_s", 0) >= 1:
            bits.append(f"passou {_fmt(m['tempo_perto_de_outra_s'], 0)} s a menos de 1 cm de outra mosca")
        sub = m.get("tempo_no_subsolo_s", 0)
        if sub >= 1:
            bits.append(f"esteve {_fmt(sub, 0)} s no laboratório")
        if m.get("capturas", 0):
            bits.append(f"foi capturada {m['capturas']}×")
        art = "a" if f["sex"] == "female" else "o"
        L.append(f"- **{f['name']}** ({'fêmea' if f['sex'] == 'female' else 'macho'}, {f.get('hud', '')}): " + ", ".join(bits) + ".")
    L.append("")
    # encontros e social
    L.append("## Encontros")
    enc = [e for e in events if e["kind"] == "encontro"]
    if not enc:
        L.append("Ninguém chegou a menos de 1 cm de ninguém. Sem reflexo de aproximação social confirmado, cruzar-se é acaso.")
    else:
        mf = [e for e in enc if e.get("sexos") in ("fm", "mf")]
        L.append(f"{len(enc)} encontros, {len(mf)} entre macho e fêmea: " + "; ".join(f"{e['flies'][0]} e {e['flies'][1]} aos {_fmt(e['t'], 0)} s" for e in enc[:6]) + ("…" if len(enc) > 6 else "") + ".")
    soc = Counter(e["kind"] for e in events if e["kind"] in ("comeram_juntas", "dancaram", "jogaram_bola", "flerte_aceito", "flerte_rejeitado", "jogaram_cartas", "apostou", "ganhou_na_roleta", "perdeu_na_roleta"))
    if soc:
        nomes = {'comeram_juntas': 'refeições a dois', 'dancaram': 'danças', 'jogaram_bola': 'partidas de bola', 'flerte_aceito': 'flertes aceitos', 'flerte_rejeitado': 'flertes rejeitados',
                 'jogaram_cartas': 'partidas de cartas', 'apostou': 'apostas na roleta', 'ganhou_na_roleta': 'vitórias na roleta', 'perdeu_na_roleta': 'derrotas na roleta'}
        L.append("Vida social (camada gamificada): " + ", ".join(f"{nomes[k]} {v}" for k, v in soc.items()) + ".")
        for e in [e for e in events if e["kind"] == "jogaram_cartas"][:3]:
            L.append(f"- Partida de cartas entre {', '.join(e['flies'])} aos {_fmt(e['t'], 0)} s: {e.get('vencedor')} levou as fichas.")
        for e in [e for e in events if e["kind"] == "ganhou_na_roleta"][:3]:
            L.append(f"- {e['flies'][0]} ganhou {e.get('fichas')} fichas na roleta aos {_fmt(e['t'], 0)} s (saldo {e.get('saldo')}).")
        for e in [e for e in events if e["kind"] in ("flerte_aceito", "flerte_rejeitado", "dancaram")][:6]:
            verb = {"flerte_aceito": "flertou com", "flerte_rejeitado": "levou um fora de", "dancaram": "dançou com"}[e["kind"]]
            L.append(f"- {e['flies'][0]} {verb} {e['flies'][1]} aos {_fmt(e['t'], 0)} s.")
    songs = [e for e in events if e["kind"] == "estado" and e.get("para") == "cantando"]
    if songs:
        c = Counter(e["flies"][0] for e in songs)
        L.append("Cantaram: " + ", ".join(f"{k} ({v}×)" for k, v in c.most_common()) + ".")
    L.append("")
    # sustos, agua, esferas
    L.append("## Sustos e acidentes")
    jumps = Counter(e["flies"][0] for e in events if e["kind"] == "salto")
    if jumps:
        L.append("Saltos de fuga: " + ", ".join(f"{k} {v}×" for k, v in jumps.most_common()) + (". Uma cascata: o salto de uma vira vulto para as outras." if sum(jumps.values()) > 20 else "."))
        motivos = Counter(e.get("motivo", "?") for e in events if e["kind"] == "salto")
        L.append("Motivos dos sustos: " + "; ".join(f"{m_} ({v}×)" for m_, v in motivos.most_common(4)) + ".")
    else:
        L.append("Nenhum salto de fuga.")
    for e in events:
        if e["kind"] == "presa_na_agua":
            L.append(f"- {e['flies'][0]} ficou presa no lago aos {_fmt(e['t'], 0)} s.")
        elif e["kind"] == "resgate_da_agua":
            L.append(f"- {e['flies'][1]} encostou em {e['flies'][0]} e a libertou do lago aos {_fmt(e['t'], 0)} s.")
        elif e["kind"] == "afundou":
            L.append(f"- {e['flies'][0]} afundou pelo fundo falso do lago e caiu no laboratório aos {_fmt(e['t'], 0)} s.")
        elif e["kind"] == "esfera_empurrada":
            L.append(f"- {e['flies'][0]} empurrou {e.get('objeto', 'uma esfera')} aos {_fmt(e['t'], 0)} s.")
    L.append("")
    # laboratorio
    L.append("## O laboratório")
    lab_ev = [e for e in events if e["kind"] in ("entrou_no_lab", "captura", "soltura", "robo_persegue", "robo_sai", "robo_congelado", "morreu_de_fome", "voltou_iluminada")]
    if not lab_ev:
        L.append("Ninguém entrou no subsolo. Os robôs patrulharam salas vazias.")
    for e in lab_ev:
        if e["kind"] == "entrou_no_lab":
            L.append(f"- {e['flies'][0]} entrou no laboratório pela {e.get('via', '?')} aos {_fmt(e['t'], 0)} s.")
        elif e["kind"] == "robo_persegue":
            L.append(f"- {e.get('robot')} foi atrás de {e['flies'][0]} aos {_fmt(e['t'], 0)} s.")
        elif e["kind"] == "captura":
            L.append(f"- {e.get('robot')} capturou {e['flies'][0]} aos {_fmt(e['t'], 0)} s (contato prolongado sem fuga).")
        elif e["kind"] == "soltura":
            L.append(f"- {e.get('robot')} devolveu {e['flies'][0]} à superfície aos {_fmt(e['t'], 0)} s.")
        elif e["kind"] == "robo_sai":
            L.append(f"- Anoiteceu: {e.get('robot')} saiu para a manutenção da superfície aos {_fmt(e['t'], 0)} s.")
        elif e["kind"] == "robo_congelado":
            L.append(f"- Gerador desligado: {e.get('robot')} congelou aos {_fmt(e['t'], 0)} s.")
        elif e["kind"] == "morreu_de_fome":
            L.append(f"- {e['flies'][0]} MORREU DE FOME no laboratório aos {_fmt(e['t'], 0)} s, depois de {_fmt(e.get('sem_comer_s', 0), 0)} s lá embaixo sem comer. No subsolo não há comida.")
        elif e["kind"] == "voltou_iluminada":
            L.append(f"- {e['flies'][0]} voltou à superfície aos {_fmt(e['t'], 0)} s falando de um mundo mágico que viu lá embaixo.")
    L.append("")
    # o mundo magico
    fe = [e for e in events if e["kind"] in ("acreditou_no_mundo_magico", "achou_maluca", "revolucao")]
    if fe:
        L.append("## O mundo mágico")
        for e in fe:
            if e["kind"] == "acreditou_no_mundo_magico":
                L.append(f"- {e['flies'][1]} ouviu {e['flies'][0]} e acreditou no mundo mágico aos {_fmt(e['t'], 0)} s (chance {e.get('chance')}).")
            elif e["kind"] == "achou_maluca":
                L.append(f"- {e['flies'][0]} ouviu {e['flies'][1]} e achou que ela enlouqueceu, aos {_fmt(e['t'], 0)} s.")
            else:
                L.append(f"- REVOLUÇÃO aos {_fmt(e['t'], 0)} s: {', '.join(e['flies'])} acreditam no mundo mágico e marcham para o laboratório.")
        L.append("")
    # segredos
    L.append("## Segredos")
    names = {"S1": "placa dupla", "S2": "corredor de corte", "S3": "alavanca do gerador", "S4": "elevador"}
    any_s = False
    for k, nm in names.items():
        s = secrets.get(k, {})
        if s.get("disparou"):
            any_s = True
            L.append(f"- **{k} ({nm}) DISPAROU {s['disparou']}×**: " + "; ".join(f"{', '.join(e['flies'])} aos {_fmt(e['t'], 0)} s" for e in s["eventos"] if e["kind"] == "fired") + ".")
        elif s.get("quase"):
            any_s = True
            L.append(f"- {k} ({nm}): chegou perto {s['quase']}× (" + ", ".join(", ".join(e["flies"]) for e in s["eventos"][:3] if e["kind"] == "near") + ").")
    if secrets.get("fugiram"):
        L.append(f"- **FUGA**: {', '.join(secrets['fugiram'])} subiram no elevador e saíram do mundo.")
    if not any_s:
        L.append("Nenhum segredo chegou perto de disparar. O experimento continua.")
    if interventions:
        L.append("")
        L.append("## Intervenções do laboratório em vigor")
        for iv in interventions[-3:]:
            L.append(f"- {iv.get('date')}: {iv.get('what')}")
    return "\n".join(L) + "\n"
