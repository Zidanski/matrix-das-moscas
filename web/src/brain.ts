// Painel do cerebro: nuvem de somas (coordenadas do proprio conectoma da mosca)
// acendendo com os disparos gravados, e tracos das taxas de entrada/saida.
import * as THREE from "three";
import type { Replay } from "./replay";

const CLASS_COLORS = [0x556270, 0xf4a261, 0x8ecae6, 0x5a7d9a, 0xffd166, 0xff7b54, 0x9bf6ff, 0x7c6f9f, 0xc77dff];

export class BrainCloud {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(40, 1, 0.01, 50);
  points?: THREE.Points;
  base!: Float32Array;       // cores de repouso
  colors!: Float32Array;     // cores atuais
  sizes!: Float32Array;
  heat!: Float32Array;       // decaimento por neuronio
  n = 0;
  fly = -1;
  angle = 0;
  constructor() {
    this.camera.position.set(0, 0.6, 2.6);
    this.camera.lookAt(0, 0, 0);
  }
  somaArrays: Record<number, Float32Array> = {};   // ao vivo: somas vindas do hello
  async load(rp: Replay, dir: string, fly: number) {
    if (this.points) { this.scene.remove(this.points); this.points.geometry.dispose(); }
    this.fly = fly;
    let data: Float32Array;
    if (this.somaArrays[fly]) data = this.somaArrays[fly];
    else {
      const r = await fetch(`/runs/${dir}/soma_${fly}.bin`);
      if (!r.ok) { this.n = 0; return; }
      data = new Float32Array(await r.arrayBuffer());
    }
    this.n = data.length / 4;
    const pos = new Float32Array(this.n * 3);
    this.base = new Float32Array(this.n * 3);
    this.colors = new Float32Array(this.n * 3);
    this.sizes = new Float32Array(this.n);
    this.heat = new Float32Array(this.n);
    const c = new THREE.Color();
    for (let i = 0; i < this.n; i++) {
      pos[i * 3] = data[i * 4]; pos[i * 3 + 1] = -data[i * 4 + 1]; pos[i * 3 + 2] = data[i * 4 + 2];   // y do EM cresce para baixo
      c.set(CLASS_COLORS[data[i * 4 + 3] | 0] ?? 0x556270).multiplyScalar(0.35);
      this.base.set([c.r, c.g, c.b], i * 3);
      this.sizes[i] = 0.012;
    }
    this.colors.set(this.base);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(this.colors, 3));
    const mat = new THREE.PointsMaterial({ size: 0.014, vertexColors: true, transparent: true, opacity: 0.95, sizeAttenuation: true, depthWrite: false, blending: THREE.AdditiveBlending });
    this.points = new THREE.Points(geo, mat);
    this.scene.add(this.points);
    void rp;
  }
  /** acende os neuronios que dispararam neste tick; decai os demais */
  update(fired: Uint16Array, dt: number) {
    if (!this.points) return;
    const decay = Math.exp(-dt / 0.12);
    for (let i = 0; i < this.n; i++) this.heat[i] *= decay;
    for (let k = 0; k < fired.length; k++) this.heat[fired[k]] = 1.0;
    const col = this.colors;
    for (let i = 0; i < this.n; i++) {
      const h = this.heat[i];
      const b = i * 3;
      col[b] = this.base[b] + h * (1.0 - this.base[b]);
      col[b + 1] = this.base[b + 1] + h * (0.95 - this.base[b + 1]);
      col[b + 2] = this.base[b + 2] + h * (0.6 - this.base[b + 2]);
    }
    (this.points.geometry.getAttribute("color") as THREE.BufferAttribute).needsUpdate = true;
    this.angle += dt * 0.25;
    this.points.rotation.y = this.angle;
  }
}

/** Tracos de taxas: pequenos sparklines em canvas 2D. */
export class Traces {
  ctx: CanvasRenderingContext2D;
  constructor(public canvas: HTMLCanvasElement, public pops: { key: string; label: string; color: string; max: number }[]) {
    this.ctx = canvas.getContext("2d")!;
  }
  draw(rp: Replay, fly: number, k: number, window = 400) {
    const W = this.canvas.width, H = this.canvas.height;
    const ctx = this.ctx;
    ctx.clearRect(0, 0, W, H);
    const rowH = H / this.pops.length;
    const k0 = Math.max(0, k - window);
    this.pops.forEach((p, r) => {
      const y0 = r * rowH;
      ctx.fillStyle = "rgba(255,255,255,0.05)"; ctx.fillRect(0, y0, W, rowH - 2);
      if (!(p.key in rp.fi)) return;
      ctx.strokeStyle = p.color; ctx.lineWidth = 1.2; ctx.beginPath();
      let maxv = 0;
      for (let j = k0; j <= k; j++) {
        const v = rp.get(j, fly, p.key); if (v > maxv) maxv = v;
        const x = ((j - k0) / window) * W;
        const y = y0 + rowH - 2 - Math.min(1, v / p.max) * (rowH - 6);
        if (j === k0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.fillStyle = p.color; ctx.font = "10px system-ui"; ctx.fillText(`${p.label} ${rp.get(k, fly, p.key).toFixed(1)}`, 4, y0 + 10);
    });
  }
}
