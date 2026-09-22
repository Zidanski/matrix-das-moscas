// Modo AO VIVO: recebe ticks por WebSocket e expoe a mesma interface do Replay.
import { Replay, type Manifest, type ReplayEvent } from "./replay";

export class LiveReplay extends Replay {
  cap = 0;
  somaCache: Record<number, Float32Array> = {};
  spikesByTick: Map<number, Uint16Array[]> = new Map();
  constructor(m: Manifest) {
    super(m, new Float32Array(0), new Float32Array(0), [], new Float32Array(0));
    this.manifest.ticks = 0;
    this.grow(2000);
  }
  grow(n: number) {
    const nf = this.nf;
    const f = new Float32Array(n * this.manifest.n_flies * nf); f.set(this.frames);
    const o = new Float32Array(n * Math.max(1, this.manifest.n_spheres) * 2); o.set(this.objects);
    const w = new Float32Array(n * Math.max(1, this.rowLen)); w.set(this.world);
    this.frames = f; this.objects = o; this.world = w; this.cap = n;
  }
  push(msg: any) {
    const k: number = msg.tick;
    if (k >= this.cap) this.grow(this.cap * 2);
    const nf = this.nf, nfl = this.manifest.n_flies;
    for (let i = 0; i < nfl; i++) this.frames.set(msg.rows[i], (k * nfl + i) * nf);
    const ns = this.manifest.n_spheres;
    for (let i = 0; i < Math.min(ns, msg.spheres.length); i++) this.objects.set(msg.spheres[i], (k * ns + i) * 2);
    if (this.rowLen) this.world.set(msg.world.slice(0, this.rowLen), k * this.rowLen);
    this.spikesByTick.set(k, (msg.fired as number[][]).map((a) => Uint16Array.from(a)));
    if (this.spikesByTick.size > 400) this.spikesByTick.delete(k - 400);
    for (const e of msg.events as ReplayEvent[]) this.events.push(e);
    this.manifest.ticks = k + 1;
    this.manifest.seconds = Math.max(this.manifest.seconds, (k + 1) * this.manifest.dt_s);
  }
  spikes(tick: number, fly: number): Uint16Array {
    return this.spikesByTick.get(tick)?.[fly] ?? new Uint16Array(0);
  }
}

export type LiveHandlers = {
  onHello: (m: Manifest, soma: number[][]) => void;
  onTick: (msg: any) => void;
  onChanges: (changes: any[]) => void;
  onEnd: (msg: any) => void;
  onStatus: (s: string) => void;
};

export class LiveClient {
  ws: WebSocket | null = null;
  constructor(public url: string, public h: LiveHandlers) {}
  connect() {
    this.h.onStatus("conectando…");
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.onopen = () => this.h.onStatus("ao vivo");
    ws.onclose = () => this.h.onStatus("desconectado");
    ws.onerror = () => this.h.onStatus("erro: servidor ao vivo não encontrado (uv run matrix live)");
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === "hello") this.h.onHello(m, m.soma);
      else if (m.type === "tick") { if (m.changes?.length) this.h.onChanges(m.changes); this.h.onTick(m); }
      else if (m.type === "end") this.h.onEnd(m);
    };
  }
  send(cmd: any) { this.ws?.readyState === 1 && this.ws.send(JSON.stringify(cmd)); }
  close() { this.ws?.close(); this.ws = null; }
}
