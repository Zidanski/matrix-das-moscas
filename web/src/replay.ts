// Leitura do replay: manifest.json + frames.bin (float32 [ticks, flies, fields]) + objects.bin + events.json

export interface FlyInfo { name: string; sex: "female" | "male"; color: string; hud: string; n_neurons: number; control: boolean; }
export interface Manifest {
  world: any; dt_s: number; seconds: number; ticks: number; n_flies: number; n_spheres: number;
  fields: string[]; flies: FlyInfo[]; spheres: any[]; cubes: any[]; prisms: any[]; patches: any[]; water: any[]; playgrounds?: any[];
  state_ids: Record<string, number>; metrics?: any; brain_mode: string; day_index?: number; wall_s?: number;
  robots?: { name: string; level: string; route: number[][]; r: number; night_only: boolean }[]; n_robots?: number;
  world_row_len?: number; robot_fields?: string[]; lab_fields?: string[]; level_ids?: Record<string, number>;
  diary?: string; secrets?: any;
  brain_samples?: { fly: number; n: number; n_total: number; class_names: string[] }[];
  spikes?: { n: number };
}
export interface ReplayEvent { t: number; kind: string; flies: string[]; [k: string]: any; }

export class Replay {
  fi: Record<string, number> = {};
  stateNames: Record<number, string> = {};
  spikePtr: Int32Array | null = null;
  spikeIdx: Uint16Array | null = null;
  constructor(public manifest: Manifest, public frames: Float32Array, public objects: Float32Array, public events: ReplayEvent[], public world: Float32Array = new Float32Array(0)) {
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
  get rowLen() { return this.manifest.world_row_len ?? 0; }
  robot(tick: number, i: number): { x: number; y: number; lab: boolean; state: number } {
    const o = tick * this.rowLen + i * 4;
    return { x: this.world[o], y: this.world[o + 1], lab: this.world[o + 2] > 0.5, state: this.world[o + 3] };
  }
  labState(tick: number): { door: boolean; hatch: boolean; genOff: boolean; elevator: boolean } {
    const nr = this.manifest.n_robots ?? 0;
    const o = tick * this.rowLen + nr * 4;
    if (!this.rowLen) return { door: false, hatch: false, genOff: false, elevator: false };
    return { door: this.world[o] > 0.5, hatch: this.world[o + 1] > 0.5, genOff: this.world[o + 2] > 0.5, elevator: this.world[o + 3] > 0.5 };
  }
  spikes(tick: number, fly: number): Uint16Array {
    if (!this.spikePtr || !this.spikeIdx) return new Uint16Array(0);
    const k = tick * this.manifest.n_flies + fly;
    return this.spikeIdx.subarray(this.spikePtr[k], this.spikePtr[k + 1]);
  }
  level(tick: number, fly: number): number { return this.fi["level"] !== undefined ? this.get(tick, fly, "level") : 0; }
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
  let wb = new ArrayBuffer(0);
  if (m.world_row_len) { const r = await fetch(`/runs/${dir}/world.bin`); if (r.ok) wb = await r.arrayBuffer(); }
  const rp = new Replay(m, new Float32Array(fb), new Float32Array(ob), ev, new Float32Array(wb));
  if (m.spikes) {
    const [sp, si] = await Promise.all([fetch(`/runs/${dir}/spikes_ptr.bin`), fetch(`/runs/${dir}/spikes.bin`)]);
    if (sp.ok && si.ok) { rp.spikePtr = new Int32Array(await sp.arrayBuffer()); rp.spikeIdx = new Uint16Array(await si.arrayBuffer()); }
  }
  return rp;
}
