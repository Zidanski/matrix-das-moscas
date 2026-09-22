// Dossie estilo Dwarf Fortress: tracos, relacoes e ultimas interacoes de uma mosca.
// Tudo derivado do replay (eventos + campos). Relacoes vem dos eventos da camada social.
import type { Replay, ReplayEvent } from "./replay";
import { likes } from "./mood";

const HEART = "♥";

const EVENT_TEXT: Record<string, (e: ReplayEvent, me: string, other: string) => string> = {
  encontro: (_e, _me, o) => `encontrou ${o}`,
  comeram_juntas: (_e, _me, o) => `comeu junto com ${o}`,
  dancaram: (_e, _me, o) => `dançou com ${o}`,
  jogaram_bola: (e, me, o) => (e.flies[0] === me ? `chutou a bola para ${o}` : `recebeu a bola de ${o}`),
  flerte_aceito: (e, me, o) => (e.flies[0] === me ? `flertou com ${o} e foi correspondido` : `aceitou o flerte de ${o}`),
  flerte_rejeitado: (e, me, o) => (e.flies[0] === me ? `flertou com ${o} e levou um fora` : `rejeitou ${o}`),
  salto: () => "saltou de susto",
  presa_na_agua: () => "ficou presa no lago",
  resgate_da_agua: (e, me, o) => (e.flies[0] === me ? `foi libertada do lago por ${o}` : `libertou ${o} do lago`),
  afundou: () => "afundou pelo fundo falso do lago e caiu no laboratório",
  entrou_no_lab: (e) => `entrou no laboratório pela ${e.via ?? "?"}`,
  robo_persegue: (e) => `foi perseguida por ${e.robot}`,
  captura: (e) => `foi capturada por ${e.robot}`,
  soltura: (e) => `foi devolvida à superfície por ${e.robot}`,
  esfera_empurrada: (e) => `empurrou ${e.objeto}`,
  segredo_quase: (e) => `chegou perto de acionar ${e.secret}`,
  segredo_disparado: (e) => `ACIONOU ${e.secret}!`,
  fuga: () => "FUGIU pelo elevador",
  modo_deus: (e) => `sofreu intervenção divina: ${e.comando}`,
};

export function relations(rp: Replay, me: string, tUpTo: number) {
  const rel: Record<string, { amizade: number; romance: number }> = {};
  const get = (o: string) => (rel[o] ??= { amizade: 0, romance: 0 });
  for (const e of rp.events) {
    if (e.t > tUpTo || !e.flies.includes(me) || e.flies.length < 2) continue;
    const o = e.flies.find((f) => f !== me)!;
    switch (e.kind) {
      case "encontro": get(o).amizade += 0.05; break;
      case "comeram_juntas": get(o).amizade += 0.15; break;
      case "dancaram": get(o).amizade += 0.2; break;
      case "jogaram_bola": get(o).amizade += 0.15; break;
      case "flerte_aceito": get(o).romance += 0.3; get(o).amizade += 0.05; break;
      case "flerte_rejeitado": get(o).romance += 0.08; break;
      case "resgate_da_agua": get(o).amizade += 0.3; break;
    }
  }
  return rel;
}

export function traits(rp: Replay, k: number, i: number): string[] {
  const m = rp.manifest;
  const name = m.flies[i].name;
  const t = k * m.dt_s;
  const out: string[] = [];
  const my = rp.events.filter((e) => e.t <= t && e.flies.includes(name));
  const cnt = (kind: string) => my.filter((e) => e.kind === kind).length;
  // gostos derivados do que a mosca fez
  let water = 0, sugar = 0, ball = 0, lab = 0;
  const step = Math.max(1, Math.floor(k / 300));
  for (let j = 0; j <= k; j += step) {
    if (rp.fi["in_water_L"] !== undefined && Math.max(rp.get(j, i, "in_water_L"), rp.get(j, i, "in_water_R")) > 0.3) water++;
    if (rp.fi["in_sugar_L"] !== undefined && Math.max(rp.get(j, i, "in_sugar_L"), rp.get(j, i, "in_sugar_R")) > 0.3) sugar++;
    if (rp.fi["level"] !== undefined && rp.get(j, i, "level") === 1) lab++;
  }
  ball = cnt("esfera_empurrada") + cnt("jogaram_bola");
  const n = Math.max(1, Math.floor(k / step) + 1);
  if (water / n > 0.05) out.push(`${name} gosta de água`);
  if (sugar / n > 0.1) out.push(`${name} gosta de açúcar`);
  if (ball >= 2) out.push(`${name} gosta de jogar bola`);
  if (cnt("dancaram") >= 2) out.push(`${name} adora dançar`);
  if (cnt("salto") > 20) out.push(`${name} é assustadiça`);
  else if (cnt("salto") === 0 && k > 500) out.push(`${name} é destemida`);
  if (lab / n > 0.2) out.push(`${name} é curiosa: vive no laboratório`);
  if (cnt("captura") > 0) out.push(`${name} já foi capturada ${cnt("captura")}×`);
  if (m.flies[i].sex === "male" && cnt("flerte_aceito") + cnt("flerte_rejeitado") >= 2) out.push(`${name} é galanteador`);
  if (cnt("flerte_rejeitado") > cnt("flerte_aceito") && cnt("flerte_rejeitado") >= 2) out.push(`${name} vive levando fora`);
  const gam = rp.fi["gamified"] !== undefined ? rp.get(k, i, "gamified") : 0;
  out.push(gam > 0 ? `agora movida pela camada Sims (desejo)` : `agora movida pelo cérebro (reflexo)`);
  for (const l of likes(rp, k, i)) out.push(`gosta de ${l}`);
  return out;
}

export function relationLines(rp: Replay, k: number, i: number): string[] {
  const m = rp.manifest;
  const name = m.flies[i].name;
  const rel = relations(rp, name, k * m.dt_s);
  const lines: string[] = [];
  for (const [o, r] of Object.entries(rel).sort((a, b) => b[1].romance + b[1].amizade - a[1].romance - a[1].amizade)) {
    const parts: string[] = [];
    if (r.romance >= 0.6) parts.push(`apaixonad${m.flies[i].sex === "male" ? "o" : "a"} por ${o} ${HEART.repeat(3)}`);
    else if (r.romance >= 0.3) parts.push(`tem interesse romântico em ${o} ${HEART.repeat(2)}`);
    else if (r.romance > 0) parts.push(`já flertou com ${o} ${HEART}`);
    if (r.amizade >= 0.6) parts.push(`melhor amig${m.flies[i].sex === "male" ? "o" : "a"} de ${o}`);
    else if (r.amizade >= 0.3) parts.push(`amig${m.flies[i].sex === "male" ? "o" : "a"} de ${o}`);
    else if (r.amizade > 0) parts.push(`conhece ${o}`);
    if (parts.length) lines.push(`${name} ${parts.join("; ")}`);
  }
  return lines.length ? lines : [`${name} ainda não tem relações`];
}

export function recentLog(rp: Replay, k: number, i: number, max = 14): string[] {
  const m = rp.manifest;
  const name = m.flies[i].name;
  const t = k * m.dt_s;
  const out: string[] = [];
  for (let j = rp.events.length - 1; j >= 0 && out.length < max; j--) {
    const e = rp.events[j];
    if (e.t > t || !e.flies.includes(name) || e.kind === "estado") continue;
    const other = e.flies.find((f) => f !== name) ?? "";
    const f = EVENT_TEXT[e.kind];
    if (!f) continue;
    out.push(`${e.t.toFixed(1).replace(".", ",")} s — ${name} ${f(e, name, other)}`);
  }
  return out.length ? out : ["(nada aconteceu com ela ainda)"];
}

export function needsBars(rp: Replay, k: number, i: number): string {
  if (rp.fi["need_social"] === undefined) return "";
  const bar = (v: number) => "▮".repeat(Math.round(v * 10)) + "▯".repeat(10 - Math.round(v * 10));
  const h = Math.min(1, (rp.get(k, i, "hunger") - 1));
  return `fome ${bar(h)}  social ${bar(rp.get(k, i, "need_social"))}  diversão ${bar(rp.get(k, i, "need_fun"))}  romance ${bar(rp.get(k, i, "need_romance"))}`;
}
