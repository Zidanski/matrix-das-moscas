// Camada "The Sims": humor, pensamentos e gostos de cada mosca.
// TUDO aqui e LEITURA do replay (sensores registrados, estado, fome, taxas): nada
// influencia o comportamento, e nada e inventado. Um pensamento so aparece se o
// sensor correspondente estava ativo naquele instante.
import type { Replay } from "./replay";

export interface Mood { emoji: string; word: string; color: string; }

const THOUGHTS: [string, string, string][] = [
  // [campo de entrada (sem _L/_R), emoji, legenda]
  ["sugar", "🍬", "açúcar"], ["water", "💧", "água"], ["bitter", "🤢", "amargo"],
  ["orn_dm1", "🍎", "cheiro de comida"], ["orn_v", "💨", "CO₂"], ["orn_da2", "🍄", "geosmina"],
  ["orn_da1", "♂", "cVA (macho perto)"], ["ppk23", "🤝", "contato"], ["jo_a", "🎵", "canção"],
  ["jo_ce", "👆", "toque na antena"], ["lc4", "⚠️", "vulto!"], ["lc11", "🐝", "algo se mexe"],
  ["leg_grn", "🦶", "pisa em algo"],
];

export function thoughts(rp: Replay, k: number, i: number, min = 0.15): { emoji: string; label: string; v: number }[] {
  const out: { emoji: string; label: string; v: number }[] = [];
  for (const [f, emoji, label] of THOUGHTS) {
    const l = rp.fi[`in_${f}_L`], r = rp.fi[`in_${f}_R`];
    if (l === undefined) continue;
    const v = Math.max(rp.frames[(k * rp.manifest.n_flies + i) * rp.nf + l], rp.frames[(k * rp.manifest.n_flies + i) * rp.nf + r]);
    if (v >= min) out.push({ emoji, label, v });
  }
  return out.sort((a, b) => b.v - a.v).slice(0, 3);
}

/** Humor derivado: estado atual, fome, salto recente, convulsão, presa. */
export function mood(rp: Replay, k: number, i: number): Mood {
  const st = rp.stateNames[rp.get(k, i, "state")];
  const hunger = rp.get(k, i, "hunger");
  if (rp.get(k, i, "ignited") > 0) return { emoji: "😵", word: "convulsão", color: "#e63946" };
  if (st === "presa") return { emoji: "😰", word: "presa na água", color: "#4cc9f0" };
  if (st === "capturada") return { emoji: "🤖", word: "capturada", color: "#adb5bd" };
  // salto nos ultimos 2 s -> assustada
  const back = Math.max(0, k - Math.round(2 / rp.manifest.dt_s));
  for (let j = k; j >= back; j -= 4) if (rp.get(j, i, "jump") > 0 || rp.stateNames[rp.get(j, i, "state")] === "saltando") return { emoji: "😱", word: "assustada", color: "#ff7b54" };
  if (st === "comendo") return { emoji: "😋", word: "comendo, feliz", color: "#7ee787" };
  if (st === "dancando") return { emoji: "💃", word: "dançando", color: "#ffd166" };
  if (st === "jogando_bola") return { emoji: "⚽", word: "jogando bola", color: "#7ee787" };
  if (st === "jogando_cartas") return { emoji: "🃏", word: "jogando cartas", color: "#ffd166" };
  if (st === "apostando") return { emoji: "🎰", word: "apostando na roleta", color: "#ff8fab" };
  if (st === "flertando") return { emoji: "😘", word: "flertando", color: "#ff8fab" };
  if (st === "cantando" || st === "cortejando") return { emoji: "😍", word: "apaixonado", color: "#ff8fab" };
  if (hunger > 1.6) return { emoji: "😫", word: "faminta", color: "#f4a261" };
  if (hunger > 1.25) return { emoji: "😐", word: "com fome", color: "#ffd166" };
  if (st === "andando") return { emoji: "🙂", word: "passeando", color: "#a8dadc" };
  if (st === "re") return { emoji: "😬", word: "recuando", color: "#c77dff" };
  return { emoji: "😌", word: "tranquila", color: "#e6edf3" };
}

/** "Gostos": o que a mosca mais fez ate o instante k (derivado do replay). */
export function likes(rp: Replay, k: number, i: number): string[] {
  const n = Math.max(1, k);
  const dt = rp.manifest.dt_s;
  const counts: Record<string, number> = {};
  let dist = 0, px = rp.get(0, i, "x"), py = rp.get(0, i, "y");
  const step = Math.max(1, Math.floor(n / 400));
  for (let j = 0; j <= k; j += step) {
    const s = rp.stateNames[rp.get(j, i, "state")] ?? "?";
    counts[s] = (counts[s] ?? 0) + step;
    const x = rp.get(j, i, "x"), y = rp.get(j, i, "y");
    dist += Math.hypot(x - px, y - py); px = x; py = y;
  }
  const out: string[] = [];
  // "gosta de" = so o que e prazeroso/escolhido; medo (saltos) e recuo NAO sao gostos (ficam nos tracos)
  const eat = (counts["comendo"] ?? 0) * dt, walk = (counts["andando"] ?? 0) * dt, sing = (counts["cantando"] ?? 0) * dt;
  const dance = (counts["dancando"] ?? 0) * dt, ball = (counts["jogando_bola"] ?? 0) * dt, cards = (counts["jogando_cartas"] ?? 0) * dt, bet = (counts["apostando"] ?? 0) * dt;
  if (eat > 1) out.push(`comer (${eat.toFixed(0)} s)`);
  if (dist > 2) out.push(`passear (${dist.toFixed(0)} cm)`);
  if (sing > 0.5) out.push(`cantar (${sing.toFixed(0)} s)`);
  if (dance > 0.5) out.push(`dançar (${dance.toFixed(0)} s)`);
  if (ball > 0.3) out.push(`jogar bola`);
  if (cards > 0.5) out.push(`jogar cartas (${cards.toFixed(0)} s)`);
  if (bet > 0.5) out.push(`apostar na roleta (${bet.toFixed(0)} s)`);
  if (walk < 2 && eat < 1 && out.length === 0) out.push("ficar quieta");
  return out;
}
