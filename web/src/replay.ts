// Leitura do replay: manifest.json + frames.bin (float32 [ticks, flies, fields]) + objects.bin + events.json

export interface FlyInfo { name: string; sex: "female" | "male"; color: string; hud: string; n_neurons: number; control: boolean; }
export interface Manifest {
  world: any; dt_s: number; seconds: number; ticks: number; n_flies: number; n_spheres: number;
  fields: string[]; flies: FlyInfo[]; spheres: any[]; cubes: any[]; prisms: any[]; patches: any[]; water: any[];
  state_ids: Record<string, number>; metrics?: any; brain_mode: string; day_index?: number; wall_s?: number;
}
export interface ReplayEvent { t: number; kind: string; flies: string[]; [k: string]: any; }

export class Replay {
  fi: Record<string, number> = {};
  stateNames: Record<number, string> = {};
  constructor(public manifest: Manifest, public frames: Float32Array, public objects: Float32Array, public events: ReplayEvent[]) {
    manifest.fields.forEach((f, i) => (this.fi[f] = i));
    for (const [k, v] of Object.entries(manifest.state_ids)) this.stateNames[v] = k;
  }
  get nf() { return this.manifest.fields.length; }
  get(tick: number, fly: number, field: string): number {
    return this.frames[(tick * this.manifest.n_flies + fly) * this.nf + this.fi[field]];
  }
  sphere(tick: number, i: number): [number, number] {
    const o = (tick * this.manifest.n_spheres + i) * 2;
    return [this.objects[o], this.objects[o + 1]];
  }
}

export async function listRuns(): Promise<string[]> {
  const r = await fetch("/runs/");
  if (!r.ok) return [];
  const top: string[] = await r.json();
  const out: string[] = [];
  for (const d of top) {
    if (d.includes(".")) continue;                 // arquivos soltos (summary.json)
    const s = await fetch(`/runs/${d}/`);
    if (!s.ok) continue;
    const items = await s.json();
    if (!Array.isArray(items)) continue;
    if (items.includes("manifest.json")) out.push(d);
    else for (const sub of items) if (typeof sub === "string" && sub.startsWith("day_")) out.push(`${d}/${sub}`);
  }
  return out.sort();
}

export async function loadReplay(dir: string): Promise<Replay> {
  const [m, fb, ob, ev] = await Promise.all([
    fetch(`/runs/${dir}/manifest.json`).then((r) => r.json()),
    fetch(`/runs/${dir}/frames.bin`).then((r) => r.arrayBuffer()),
    fetch(`/runs/${dir}/objects.bin`).then((r) => r.arrayBuffer()),
    fetch(`/runs/${dir}/events.json`).then((r) => r.json()),
  ]);
  return new Replay(m, new Float32Array(fb), new Float32Array(ob), ev);
}
