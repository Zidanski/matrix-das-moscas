// Cena low-poly: paisagem deliberadamente falsa. Leve para UHD 620: sem pos-processamento,
// sombras so do sol, geometrias simples, uma malha por objeto.
import * as THREE from "three";
import type { Manifest, FlyInfo } from "./replay";

export const SURF = { sugar: 0xffd166, bitter: 0x6a4c93, none: 0xdedede, water: 0x4cc9f0 } as const;

function hills(world: any) {
  const h: number[][] = world.arena.hills;
  return (x: number, y: number) => h.reduce((z, [hx, hy, s, a]) => z + a * Math.exp(-((x - hx) ** 2 + (y - hy) ** 2) / (2 * s * s)), 0);
}

export class World3D {
  scene = new THREE.Scene();
  height: (x: number, y: number) => number;
  sun: THREE.DirectionalLight;
  sunMesh: THREE.Mesh;
  sky: THREE.Mesh;
  spheres: THREE.Mesh[] = [];
  flies: FlyMesh[] = [];
  robots: RobotMesh[] = [];
  labGroup = new THREE.Group();
  labDepth = 0;
  doorMesh?: THREE.Mesh; hatchMesh?: THREE.Mesh; elevatorMesh?: THREE.Mesh; labLights: THREE.Mesh[] = [];
  ground!: THREE.Mesh;
  constructor(public m: Manifest) {
    const w = m.world;
    this.height = hills(w);
    const R = w.arena.radius_cm;
    // ceu: esfera invertida com gradiente por vertex colors
    const skyGeo = new THREE.SphereGeometry(R * 4, 24, 12);
    const col = new Float32Array(skyGeo.attributes.position.count * 3);
    const pos = skyGeo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const t = THREE.MathUtils.clamp(pos.getY(i) / (R * 4), -1, 1);
      const c = new THREE.Color(0x7fc8ff).lerp(new THREE.Color(0xe9f6ff), 0.5 - 0.5 * t);
      col.set([c.r, c.g, c.b], i * 3);
    }
    skyGeo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    this.sky = new THREE.Mesh(skyGeo, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide }));
    this.scene.add(this.sky);
    // terreno: disco com colinas, cor chapada
    const seg = 96;
    const geo = new THREE.CircleGeometry(R, seg, 0, Math.PI * 2);
    const gpos = geo.attributes.position;
    const tri = new THREE.PlaneGeometry(6 * R, 6 * R, seg * 2, seg * 2);
    const tpos = tri.attributes.position;
    for (let i = 0; i < tpos.count; i++) {
      const x = tpos.getX(i), y = tpos.getY(i);
      const d = Math.hypot(x, y);
      const zz = d <= R ? this.height(x, y) : -0.4;   // fora da arena: chao plano um pouco mais baixo
      tpos.setZ(i, zz);
    }
    tri.rotateX(-Math.PI / 2);   // plano XY (z = altura) -> three (y = altura, z = -y)
    tri.computeVertexNormals();
    const ground = new THREE.Mesh(tri, new THREE.MeshLambertMaterial({ color: 0x76c442, flatShading: true, transparent: true }));
    ground.receiveShadow = true;
    this.scene.add(ground);
    this.ground = ground;
    void gpos;
    // borda da arena
    const ring = new THREE.Mesh(new THREE.TorusGeometry(R, 0.3, 6, 64), new THREE.MeshLambertMaterial({ color: 0x5aa832 }));
    ring.rotation.x = Math.PI / 2;
    this.scene.add(ring);
    // luz: sol geometrico (octaedro) + direcional com sombra barata
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x4c8a2a, 0.55));
    this.sun = new THREE.DirectionalLight(0xfff2cc, 1.4);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(1024, 1024);
    const sc = this.sun.shadow.camera as THREE.OrthographicCamera;
    sc.left = sc.bottom = -R; sc.right = sc.top = R; sc.near = 1; sc.far = 400;
    this.scene.add(this.sun);
    this.sunMesh = new THREE.Mesh(new THREE.OctahedronGeometry(4, 0), new THREE.MeshBasicMaterial({ color: 0xffe066 }));
    this.scene.add(this.sunMesh);
    // nuvens em caixas
    for (let i = 0; i < 7; i++) {
      const c = new THREE.Mesh(new THREE.BoxGeometry(6 + i, 2.5, 4), new THREE.MeshLambertMaterial({ color: 0xffffff }));
      c.position.set((Math.sin(i * 2.1) * 0.8) * R, 30 + (i % 3) * 4, (Math.cos(i * 1.3) * 0.8) * R);
      this.scene.add(c);
    }
    // objetos
    for (const s of m.spheres) {
      const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry(s.r, 1), new THREE.MeshLambertMaterial({ color: (SURF as any)[s.surface] ?? SURF.none, flatShading: true }));
      mesh.castShadow = true;
      this.scene.add(mesh);
      this.spheres.push(mesh);
    }
    for (const c of m.cubes) {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(c.size, c.size, c.size), new THREE.MeshLambertMaterial({ color: c.hollow ? 0xff7b54 : 0xe07a5f }));
      mesh.position.set(c.x, this.height(c.x, c.y) + c.size / 2, -c.y);
      mesh.castShadow = true;
      this.scene.add(mesh);
    }
    for (const p of m.prisms) {
      const color = p.odor === "co2" ? 0x9bb1ff : p.odor === "food" ? 0xffb703 : 0xb5e48c;
      const mesh = new THREE.Mesh(new THREE.ConeGeometry(p.size / 1.4, p.size * 1.3, 3), new THREE.MeshLambertMaterial({ color, flatShading: true }));
      mesh.position.set(p.x, this.height(p.x, p.y) + p.size * 0.65, -p.y);
      mesh.castShadow = true;
      this.scene.add(mesh);
      // arvore: cone/esfera em haste
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 3, 5), new THREE.MeshLambertMaterial({ color: 0x8d6e63 }));
      stem.position.set(p.x + 3, this.height(p.x + 3, p.y) + 1.5, -p.y);
      const crown = new THREE.Mesh(new THREE.SphereGeometry(1.4, 6, 5), new THREE.MeshLambertMaterial({ color: 0x2a9d8f, flatShading: true }));
      crown.position.set(p.x + 3, this.height(p.x + 3, p.y) + 3.6, -p.y);
      this.scene.add(stem, crown);
    }
    for (const p of m.patches) {
      const color = p.kind === "sugar" ? SURF.sugar : p.kind === "bitter" ? SURF.bitter : 0x8fbf6a;
      const mesh = new THREE.Mesh(new THREE.CircleGeometry(p.r, 16), new THREE.MeshLambertMaterial({ color }));
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.set(p.x, this.height(p.x, p.y) + 0.03, -p.y);
      this.scene.add(mesh);
    }
    for (const wtr of m.water) {
      const mesh = new THREE.Mesh(new THREE.CircleGeometry(wtr.r, 24), new THREE.MeshLambertMaterial({ color: SURF.water, transparent: true, opacity: 0.85 }));
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.set(wtr.x, this.height(wtr.x, wtr.y) + 0.05, -wtr.y);
      mesh.userData.water = true;
      this.scene.add(mesh);
    }
    // decoracao (so visual): arvores e formas
    const decor = m.world.objects?.decor ?? {};
    for (const t of decor.trees ?? []) {
      const h = t.h ?? 4;
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.25, h * 0.55, 5), new THREE.MeshLambertMaterial({ color: 0x8d6e63 }));
      stem.position.set(t.x, this.height(t.x, t.y) + h * 0.275, -t.y);
      const crownGeo = t.kind === "cone" ? new THREE.ConeGeometry(h * 0.35, h * 0.7, 6) : new THREE.SphereGeometry(h * 0.32, 6, 5);
      const crown = new THREE.Mesh(crownGeo, new THREE.MeshLambertMaterial({ color: t.kind === "cone" ? 0x2a9d8f : 0x52b788, flatShading: true }));
      crown.position.set(t.x, this.height(t.x, t.y) + h * 0.55 + (t.kind === "cone" ? h * 0.35 : h * 0.3), -t.y);
      crown.castShadow = true;
      this.scene.add(stem, crown);
    }
    for (const sh of decor.shapes ?? []) {
      const sz = sh.size ?? 2;
      const geo = sh.kind === "pyramid" ? new THREE.ConeGeometry(sz * 0.7, sz, 4) : sh.kind === "torus" ? new THREE.TorusGeometry(sz * 0.6, sz * 0.2, 6, 14) : new THREE.CylinderGeometry(sz * 0.4, sz * 0.4, sz * 2.2, 8);
      const mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ color: new THREE.Color(sh.color ?? "#ffffff"), flatShading: true }));
      const base = this.height(sh.x, sh.y);
      mesh.position.set(sh.x, base + (sh.kind === "torus" ? sz * 0.8 : sh.kind === "column" ? sz * 1.1 : sz * 0.5), -sh.y);
      if (sh.kind === "pyramid") mesh.rotation.y = Math.PI / 4;
      mesh.castShadow = true;
      this.scene.add(mesh);
    }
    for (const f of m.flies) this.flies.push(new FlyMesh(f, this.scene));
    this.buildLab(m);
  }
  buildLab(m: Manifest) {
    const lab = m.world.lab;
    if (!lab) return;
    const D = (this.labDepth = lab.depth_cm ?? 10);
    const [x0, y0, x1, y1] = lab.bounds;
    const g = this.labGroup;
    // piso e teto frios
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, y1 - y0), new THREE.MeshLambertMaterial({ color: 0x2b3440 }));
    floor.rotation.x = -Math.PI / 2; floor.position.set((x0 + x1) / 2, -D, -(y0 + y1) / 2);
    g.add(floor);
    const wallMat = new THREE.MeshLambertMaterial({ color: 0x8fa3b8, flatShading: true });
    const H = 2.5;
    const box = (cx: number, cy: number, w: number, h: number, mat = wallMat, hh = H) => {
      const mm = new THREE.Mesh(new THREE.BoxGeometry(w, hh, h), mat); mm.position.set(cx, -D + hh / 2, -cy); return mm;
    };
    // paredes externas (finas)
    g.add(box((x0 + x1) / 2, y0, x1 - x0, 0.4), box((x0 + x1) / 2, y1, x1 - x0, 0.4), box(x0, (y0 + y1) / 2, 0.4, y1 - y0), box(x1, (y0 + y1) / 2, 0.4, y1 - y0));
    for (const [cx, cy, w, h] of lab.walls) g.add(box(cx, cy, w, h));
    const d = lab.secrets.s2_corredor.door;
    this.doorMesh = box(d.x, d.y, d.w, d.h, new THREE.MeshLambertMaterial({ color: 0xff7b54 }));
    g.add(this.doorMesh);
    const z = lab.secrets.s4_elevador.zone;
    this.elevatorMesh = new THREE.Mesh(new THREE.BoxGeometry(z.w, 0.3, z.h), new THREE.MeshLambertMaterial({ color: 0x555b66 }));
    this.elevatorMesh.position.set(z.x, -D + 0.15, -z.y);
    g.add(this.elevatorMesh);
    const [lx, ly] = lab.secrets.s3_alavanca.lever;
    const lever = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 1.6, 6), new THREE.MeshLambertMaterial({ color: 0xffd166 }));
    lever.position.set(lx, -D + 0.8, -ly); lever.rotation.z = 0.5; g.add(lever);
    const gen = box(lx, ly - 1.5, 1.5, 1.0, new THREE.MeshLambertMaterial({ color: 0x6c757d }), 1.2); g.add(gen);
    if (lab.sugar_patch) {
      const sp = new THREE.Mesh(new THREE.CircleGeometry(lab.sugar_patch.r, 12), new THREE.MeshLambertMaterial({ color: SURF.sugar }));
      sp.rotation.x = -Math.PI / 2; sp.position.set(lab.sugar_patch.x, -D + 0.03, -lab.sugar_patch.y); g.add(sp);
    }
    // telas (sala das telas): painéis que "mostram os cérebros" (F5 liga ao painel neural)
    for (let i = 0; i < 4; i++) {
      const scr = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 1.6), new THREE.MeshBasicMaterial({ color: 0x0f3d5c }));
      scr.position.set(3 + i * 4.2, -D + 1.6, -(y1 - 0.5)); g.add(scr);
    }
    // luzes frias
    for (let i = 0; i < 6; i++) {
      const l = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.1, 0.5), new THREE.MeshBasicMaterial({ color: 0xcfe8ff }));
      l.position.set(x0 + 4 + i * 6.4, -D + H - 0.1, -((y0 + y1) / 2)); g.add(l); this.labLights.push(l);
    }
    const pl = new THREE.PointLight(0x9ec5ff, 30, 60); pl.position.set(0, -D + 2, 0); g.add(pl);
    // escotilha (tampa sobre o cubo oco na superficie)
    const cube = m.cubes.find((c: any) => c.hollow);
    if (cube) {
      this.hatchMesh = new THREE.Mesh(new THREE.BoxGeometry(cube.size * 0.8, 0.15, cube.size * 0.8), new THREE.MeshLambertMaterial({ color: 0x333 }));
      this.hatchMesh.position.set(cube.x, this.height(cube.x, cube.y) + cube.size + 0.1, -cube.y);
      this.scene.add(this.hatchMesh);
    }
    for (const r of m.robots ?? []) this.robots.push(new RobotMesh(r, g, D));
    this.scene.add(g);
  }
  setLab(door: boolean, hatch: boolean, genOff: boolean, elevator: boolean) {
    if (this.doorMesh) this.doorMesh.visible = !door;
    if (this.hatchMesh) this.hatchMesh.position.y += 0; if (this.hatchMesh) this.hatchMesh.rotation.x = hatch ? -1.2 : 0;
    if (this.elevatorMesh) (this.elevatorMesh.material as THREE.MeshLambertMaterial).color.set(elevator ? 0x7ee787 : 0x555b66);
    for (const l of this.labLights) (l.material as THREE.MeshBasicMaterial).color.set(genOff ? 0x331111 : 0xcfe8ff);
  }
  setUnderground(show: boolean) {
    (this.ground.material as THREE.MeshLambertMaterial).opacity = show ? 0.25 : 1.0;
    this.labGroup.visible = true;
  }
  /** coordenadas do mundo (x, y no plano, z altura) -> three (x, y=altura, z=-y) */
  toThree(x: number, y: number, z = 0): THREE.Vector3 { return new THREE.Vector3(x, this.height(x, y) + z, -y); }
  setLight(light: number) {
    // sol gira: luz = 0.5+0.5cos(2pi t/T)
    const ang = Math.acos(THREE.MathUtils.clamp(light * 2 - 1, -1, 1));
    const R = this.m.world.arena.radius_cm;
    const sx = Math.cos(ang) * R * 1.5, sy = Math.max(2, Math.sin(ang) * R * 1.2);
    this.sun.position.set(sx, sy, R * 0.6);
    this.sunMesh.position.set(sx * 2, sy * 2 + 10, R * 1.2);
    this.sun.intensity = 0.3 + 1.2 * light;
    (this.sky.material as THREE.MeshBasicMaterial).color.setScalar(0.25 + 0.75 * light);
  }
  setSphere(i: number, x: number, y: number, r: number) { this.spheres[i]?.position.copy(this.toThree(x, y, r)); }
  /** modo Deus: objetos criados ao vivo */
  addPatch(x: number, y: number, r: number, kind: string) {
    const color = kind === "sugar" ? SURF.sugar : kind === "bitter" ? SURF.bitter : 0x8fbf6a;
    const mesh = new THREE.Mesh(new THREE.CircleGeometry(r, 16), new THREE.MeshLambertMaterial({ color }));
    mesh.rotation.x = -Math.PI / 2; mesh.position.set(x, this.height(x, y) + 0.03, -y);
    this.scene.add(mesh);
  }
  addSphere(x: number, y: number, r: number, surface: string) {
    const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry(r, 1), new THREE.MeshLambertMaterial({ color: (SURF as any)[surface] ?? SURF.none, flatShading: true }));
    mesh.position.copy(this.toThree(x, y, r)); mesh.castShadow = true;
    this.scene.add(mesh); this.spheres.push(mesh);
  }
  addRobot(info: any) { this.robots.push(new RobotMesh(info, this.labGroup, this.labDepth)); }
}

export class RobotMesh {
  group = new THREE.Group();
  eye: THREE.Mesh;
  constructor(public info: any, parent: THREE.Object3D, public depth: number) {
    const body = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.4, 1.0), new THREE.MeshLambertMaterial({ color: 0xadb5bd, flatShading: true }));
    body.position.y = 1.0;
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.55, 8, 6), new THREE.MeshLambertMaterial({ color: 0xdee2e6, flatShading: true }));
    head.position.y = 2.0;
    this.eye = new THREE.Mesh(new THREE.SphereGeometry(0.15, 6, 4), new THREE.MeshBasicMaterial({ color: 0xff3b3b }));
    this.eye.position.set(0.45, 2.05, 0);
    for (const s of [1, -1]) {
      const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 1.2, 6), new THREE.MeshLambertMaterial({ color: 0x868e96 }));
      arm.position.set(0.3, 1.0, s * 0.85); arm.rotation.x = s * 0.4; this.group.add(arm);
    }
    const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 1.2, 8), new THREE.MeshLambertMaterial({ color: 0x343a40 }));
    wheel.rotation.z = Math.PI / 2; wheel.position.y = 0.3;
    this.group.add(body, head, this.eye, wheel);
    const label = makeLabel(info.name, "#ffffff"); label.position.y = 3.0; this.group.add(label);
    parent.add(this.group);
  }
  update(x: number, y: number, lab: boolean, state: number, height: (x: number, y: number) => number, t: number) {
    this.group.position.set(x, lab ? -this.depth : height(x, y) + 0.05, -y);
    this.group.visible = state !== 5;                          // dormindo = recolhido
    const chasing = state === 1 || state === 3;
    (this.eye.material as THREE.MeshBasicMaterial).color.set(state === 4 ? 0x222222 : chasing ? 0xff3b3b : 0x3bd1ff);
    if (state === 0 || state === 1 || state === 3) this.group.rotation.y = Math.sin(t) * 0.05;
  }
}

const STATE_WING: Record<string, number> = { parada: 0, andando: 0.15, re: 0.15, comendo: 0.05, saltando: 1.2, cantando: 0.9, presa: 0.3, convulsao: 1.5, capturada: 0, grooming: 0.1, lutando: 0.7, cortejando: 0.4, dancando: 0.6, flertando: 0.35, passeando: 0.15 };

export class FlyMesh {
  group = new THREE.Group();
  wings: THREE.Mesh[] = [];
  label: THREE.Sprite;
  bubble: THREE.Sprite;
  bubbleText = "";
  body: THREE.Mesh;
  L: number;
  constructor(public info: FlyInfo, scene: THREE.Scene) {
    const male = info.sex === "male";
    const L = male ? 0.22 : 0.28;              // dimorfismo: macho menor
    this.L = L;
    const color = new THREE.Color(info.color);
    const mat = new THREE.MeshLambertMaterial({ color, flatShading: true });
    const dark = new THREE.MeshLambertMaterial({ color: male ? 0x1b1b1b : color.clone().multiplyScalar(0.6), flatShading: true });
    const thorax = new THREE.Mesh(new THREE.SphereGeometry(L * 0.45, 6, 5), mat);
    const abdomen = new THREE.Mesh(new THREE.SphereGeometry(L * 0.55, 6, 5), dark);   // macho: abdome escuro
    abdomen.scale.set(1.4, 0.8, 0.9); abdomen.position.x = -L * 0.75;
    const head = new THREE.Mesh(new THREE.SphereGeometry(L * 0.3, 6, 5), new THREE.MeshLambertMaterial({ color: 0xb22222 }));
    head.position.x = L * 0.6;
    this.body = thorax;
    this.group.add(thorax, abdomen, head);
    for (const s of [1, -1]) {
      const w = new THREE.Mesh(new THREE.PlaneGeometry(L * 1.1, L * 0.45), new THREE.MeshBasicMaterial({ color: 0xeeeeff, transparent: true, opacity: 0.55, side: THREE.DoubleSide }));
      w.position.set(-L * 0.2, L * 0.3, s * L * 0.3);
      w.rotation.x = -Math.PI / 2;
      w.userData.side = s;
      this.group.add(w); this.wings.push(w);
    }
    for (let i = 0; i < 6; i++) {
      const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, L * 0.6, 3), dark);
      leg.position.set((i % 3 - 1) * L * 0.3, -L * 0.2, (i < 3 ? 1 : -1) * L * 0.35);
      leg.rotation.x = (i < 3 ? 1 : -1) * 0.7;
      this.group.add(leg);
    }
    this.label = makeLabel(info.name + (info.control ? " (controle)" : ""), info.color);
    this.label.position.y = L * 2.2;
    this.group.add(this.label);
    this.bubble = makeBubble("");
    this.bubble.position.y = L * 4.2;
    this.bubble.visible = false;
    this.group.add(this.bubble);
    thorax.castShadow = true;
    scene.add(this.group);
  }
  update(pos: THREE.Vector3, heading: number, state: string, t: number, moving: boolean) {
    // no chao: o corpo fica a altura das pernas
    const L = this.L;
    this.group.position.copy(pos).add(new THREE.Vector3(0, L * 0.45, 0));
    this.group.rotation.y = heading;
    this.group.rotation.z = 0;
    const a = STATE_WING[state] ?? 0.1;
    const flap = a * Math.sin(t * (state === "cantando" ? 220 : 60));
    for (const w of this.wings) w.rotation.z = w.userData.side * (0.15 + flap);
    if (state === "saltando") {
      this.group.position.y += 0.9 * Math.abs(Math.sin(t * 26));       // arco do salto
    } else if (state === "dancando") {
      this.group.rotation.y = heading + Math.sin(t * 6) * 1.2;          // danca: gira e balanca
      this.group.position.y += L * 0.3 * Math.abs(Math.sin(t * 12));
    } else if (state === "flertando") {
      this.group.rotation.z = 0.25 * Math.sin(t * 8);                   // flerte: balanca o corpo
    } else if (moving || state === "andando" || state === "re") {
      const hop = Math.abs(Math.sin(t * 16));                            // pulinhos ao andar
      this.group.position.y += L * 0.35 * hop;
      this.group.rotation.z = 0.12 * Math.sin(t * 16);
    }
  }
  setBubble(text: string) {
    if (text === this.bubbleText) return;
    this.bubbleText = text;
    this.bubble.visible = text.length > 0;
    if (text) {
      const mat = this.bubble.material as THREE.SpriteMaterial;
      mat.map?.dispose();
      mat.map = bubbleTexture(text);
      mat.needsUpdate = true;
    }
  }
}

function bubbleTexture(text: string): THREE.CanvasTexture {
  const c = document.createElement("canvas"); c.width = 256; c.height = 96;
  const g = c.getContext("2d")!;
  g.fillStyle = "rgba(255,255,255,0.92)";
  g.beginPath(); g.roundRect(8, 4, 240, 68, 18); g.fill();
  g.beginPath(); g.moveTo(118, 72); g.lineTo(138, 72); g.lineTo(128, 90); g.closePath(); g.fill();
  g.font = "44px system-ui"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillStyle = "#222";
  g.fillText(text, 128, 40);
  return new THREE.CanvasTexture(c);
}

function makeBubble(text: string): THREE.Sprite {
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: bubbleTexture(text || " "), depthTest: false, transparent: true }));
  sp.scale.set(2.2, 0.82, 1);
  return sp;
}

function makeLabel(text: string, color: string): THREE.Sprite {
  const c = document.createElement("canvas"); c.width = 256; c.height = 64;
  const g = c.getContext("2d")!;
  g.fillStyle = "rgba(0,0,0,0.55)"; g.fillRect(0, 0, c.width, c.height);
  g.font = "bold 34px system-ui"; g.fillStyle = color; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(text, 128, 32);
  const tex = new THREE.CanvasTexture(c);
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }));
  sp.scale.set(2.0, 0.5, 1);
  return sp;
}
