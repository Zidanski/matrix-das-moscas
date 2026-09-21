import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { listRuns, loadReplay, Replay } from "./replay";
import { World3D } from "./scene";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const app = $("app");
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "low-power" });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.BasicShadowMap;
app.prepend(renderer.domElement);
const camera = new THREE.PerspectiveCamera(50, 1, 0.05, 2000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

let replay: Replay | null = null;
let world: World3D | null = null;
let tick = 0, playing = false, speed = 1, selected = 0, camMode = "orbit";
let lastWall = performance.now();

function resize() {
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
}
addEventListener("resize", resize);
resize();

async function boot() {
  const runs = await listRuns();
  const sel = $<HTMLSelectElement>("run");
  sel.innerHTML = runs.map((r) => `<option value="${r}">${r}</option>`).join("") || "<option>(nenhum replay em runs/)</option>";
  sel.onchange = () => open(sel.value);
  if (runs.length) await open(runs[runs.length - 1]);
  else $("load").textContent = "nenhum replay: rode `uv run matrix simulate` e recarregue";
}

async function open(dir: string) {
  $("load").style.display = "flex";
  replay = await loadReplay(dir);
  if (world) world.scene.clear();
  world = new World3D(replay.manifest);
  const R = replay.manifest.world.arena.radius_cm;
  camera.position.set(R * 1.2, R * 1.0, R * 1.5);
  controls.target.set(0, 0, 0);
  tick = 0;
  const scrub = $<HTMLInputElement>("scrub");
  scrub.max = String(replay.manifest.ticks - 1);
  scrub.oninput = () => { tick = +scrub.value; draw(); };
  buildFlyPanel();
  buildEventMarkers();
  $("load").style.display = "none";
  draw();
}

function buildFlyPanel() {
  const div = $("flies");
  div.innerHTML = "";
  replay!.manifest.flies.forEach((f, i) => {
    const b = document.createElement("button");
    b.innerHTML = `<span class="dot" style="background:${f.color}"></span>${f.name} <span style="color:#8b98a5">${f.sex === "male" ? "♂" : "♀"}</span>`;
    b.onclick = () => { selected = i; buildFlyPanel(); draw(); };
    if (i === selected) b.classList.add("active");
    div.appendChild(b);
  });
}

const EVENT_COLORS: Record<string, string> = { encontro: "#f4a261", salto: "#e63946", presa_na_agua: "#4cc9f0", resgate_da_agua: "#7ee787", esfera_empurrada: "#ffd166", estado: "#ffffff22" };
function buildEventMarkers() {
  const div = $("events");
  div.innerHTML = "";
  const T = replay!.manifest.seconds;
  for (const e of replay!.events) {
    if (e.kind === "estado") continue;
    const s = document.createElement("span");
    s.style.left = `${(e.t / T) * 100}%`;
    s.style.background = EVENT_COLORS[e.kind] ?? "#fff";
    s.title = `${e.t.toFixed(1)} s ${e.kind} ${e.flies.join(", ")}`;
    div.appendChild(s);
  }
}

function draw() {
  if (!replay || !world) return;
  const m = replay.manifest;
  const k = Math.max(0, Math.min(m.ticks - 1, Math.floor(tick)));   // tick e fracionario durante a reproducao
  const t = k * m.dt_s;
  const light = 0.5 + 0.5 * Math.cos((2 * Math.PI * t) / m.world.arena.day_length_s);
  world.setLight(light);
  for (let i = 0; i < m.n_spheres; i++) { const [x, y] = replay.sphere(k, i); world.setSphere(i, x, y, m.spheres[i].r); }
  const sel = $<HTMLDivElement>("hudbody");
  let selPos = new THREE.Vector3();
  world.flies.forEach((fm, i) => {
    const x = replay!.get(k, i, "x"), y = replay!.get(k, i, "y");
    const heading = replay!.get(k, i, "heading");
    const state = replay!.stateNames[replay!.get(k, i, "state")] ?? "?";
    const pos = world!.toThree(x, y, 0);
    fm.update(pos, heading, state, t);
    if (i === selected) {
      selPos = pos;
      const f = m.flies[i];
      const rates = ["MN9", "gf", "odn1", "dna01", "dna02", "mdn", "p1", "pip10"].map((p) => {
        const key = `rate_${p}_all`; return key in replay!.fi ? `${p} ${replay!.get(k, i, key).toFixed(1)}` : null;
      }).filter(Boolean).join(" · ");
      sel.innerHTML = `<b style="color:${f.color}">${f.name}</b> ${f.sex === "male" ? "♂ macho" : "♀ fêmea"} — <span class="muted">${f.hud}</span><br>` +
        `estado: <b>${state}</b> · v ${replay!.get(k, i, "v").toFixed(2)} cm/s · fome ×${replay!.get(k, i, "hunger").toFixed(2)}` +
        (replay!.get(k, i, "ignited") > 0 ? ' · <b style="color:#e63946">CONVULSÃO</b>' : "") + "<br>" +
        `<span class="muted">Hz: ${rates}</span><br>` +
        `<span class="muted">${m.brain_mode === "full" ? "cérebro completo" : "cérebro reduzido"} · luz ${(light * 100).toFixed(0)} % · dia ${m.day_index ?? 0}</span>`;
    }
  });
  if (camMode === "follow") {
    const goal = selPos.clone().add(new THREE.Vector3(-4, 3, 4));
    camera.position.lerp(goal, 0.08);
    controls.target.lerp(selPos, 0.2);
  } else if (camMode === "top") {
    camera.position.lerp(new THREE.Vector3(0.01, m.world.arena.radius_cm * 2.2, 0), 0.1);
    controls.target.lerp(new THREE.Vector3(0, 0, 0), 0.2);
  }
  $<HTMLInputElement>("scrub").value = String(k);
  $("clock").textContent = `${t.toFixed(1).replace(".", ",")} s / ${m.seconds} s`;
}

function loop() {
  requestAnimationFrame(loop);
  const now = performance.now();
  const dtWall = (now - lastWall) / 1000;
  lastWall = now;
  if (replay && playing) {
    tick += (dtWall * speed) / replay.manifest.dt_s;
    if (tick >= replay.manifest.ticks) { tick = replay.manifest.ticks - 1; playing = false; $("play").textContent = "▶"; }
    draw();
  }
  controls.update();
  if (world) renderer.render(world.scene, camera);
}

$("play").onclick = () => { playing = !playing; $("play").textContent = playing ? "❚❚" : "▶"; if (replay && tick >= replay.manifest.ticks - 1) tick = 0; };
$<HTMLSelectElement>("speed").onchange = (e) => (speed = +(e.target as HTMLSelectElement).value);
$<HTMLSelectElement>("cam").onchange = (e) => (camMode = (e.target as HTMLSelectElement).value);
addEventListener("keydown", (e) => { if (e.code === "Space") { e.preventDefault(); $("play").click(); } });

boot();
loop();
