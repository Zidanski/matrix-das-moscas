import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { listRuns, loadReplay, Replay } from "./replay";
import { World3D } from "./scene";
import { mood, thoughts, likes } from "./mood";
import { BrainCloud, Traces } from "./brain";
import { LiveClient, LiveReplay } from "./live";
import { traits, relationLines, recentLog, needsBars } from "./dossier";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const app = $("app");
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "low-power" });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.BasicShadowMap;
renderer.domElement.classList.add("world");
app.prepend(renderer.domElement);
// painel do cerebro: segundo renderer num canvas proprio
const brainCanvas = $<HTMLCanvasElement>("braincanvas");
const brainRenderer = new THREE.WebGLRenderer({ canvas: brainCanvas, antialias: false, alpha: true, powerPreference: "low-power" });
brainRenderer.setPixelRatio(1);
const brain = new BrainCloud();
const traces = new Traces($<HTMLCanvasElement>("traces"), [
  { key: "in_orn_dm1_R", label: "ORN DM1 (odor)", color: "#f4a261", max: 1 },
  { key: "in_lc4_R", label: "LC4 (vulto)", color: "#e63946", max: 1 },
  { key: "rate_MN9_all", label: "MN9 (comer)", color: "#7ee787", max: 80 },
  { key: "rate_gf_all", label: "GF (salto)", color: "#ff7b54", max: 100 },
  { key: "rate_odn1_all", label: "oDN1 (marcha)", color: "#8ecae6", max: 30 },
  { key: "rate_dna02_all", label: "DNa02 (giro)", color: "#c77dff", max: 30 },
]);
let brainOn = false, matrixOn = false, brainDir = "", brainFly = -1;
let recorder: MediaRecorder | null = null;
let live: LiveClient | null = null;
let followPrev: THREE.Vector3 | null = null;
let liveFollow = true;
let liveState = "idle";
let dossierOn = false;
const LIVE = "__AO_VIVO__";
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
  sel.innerHTML = `<option value="${LIVE}">🔴 AO VIVO</option>` + runs.map((r) => `<option value="${r}">${r}</option>`).join("");
  sel.onchange = () => (sel.value === LIVE ? openLive() : open(sel.value));
  if (runs.length) await open(runs[runs.length - 1]);
  else openLive();
}

function setLiveState(st: string) {
  liveState = st;
  const label: Record<string, string> = { idle: "pronto: clique ▶ para começar", starting: "criando os 6 cérebros…", running: "ao vivo", paused: "tempo pausado", stopping: "parando e gravando o dia…" };
  $("livestatus").textContent = "🔴 " + (label[st] ?? st);
  $("play").textContent = st === "running" ? "❚❚" : "▶";
  if (st === "idle" && !replay) {
    $("load").style.display = "flex";
    $("load").innerHTML = `AO VIVO pronto. <button id="bigplay">▶ começar</button>`;
    $("bigplay").onclick = () => $("play").click();
  }
  if (st === "starting") { $("load").style.display = "flex"; $("load").textContent = "criando os 6 cérebros (20–40 s)…"; }
  if (st === "running" || st === "paused") $("load").style.display = "none";
}

function openLive() {
  if (live) live.close();
  document.body.classList.add("live");
  $<HTMLSelectElement>("run").value = LIVE;
  $("load").style.display = "flex"; $("load").textContent = "conectando ao servidor ao vivo…";
  brainDir = ""; brainFly = -1; replay = null; liveFollow = true;
  $("hudbody").innerHTML = '<span class="muted">ao vivo: nenhum dia em curso ainda</span>';
  $("flies").innerHTML = "";
  $("events").innerHTML = "";
  live = new LiveClient("ws://localhost:8765", {
    onStatus: (st) => { if (st.startsWith("erro") || st === "desconectado") $("livestatus").textContent = "🔴 " + st + " — o servidor sobe com `npm run dev`"; },
    onState: (st) => setLiveState(st),
    onHello: (m, soma) => {
      replay = new LiveReplay(m);
      soma.forEach((arr, i) => { if (arr.length) brain.somaArrays[i] = Float32Array.from(arr); });
      if (world) world.scene.clear();
      world = new World3D(m);
      const R = m.world.arena.radius_cm;
      camera.position.set(R * 1.2, R * 1.0, R * 1.5); controls.target.set(0, 0, 0);
      tick = 0; buildFlyPanel(); buildEventMarkers();
      $("load").style.display = "none";
      $("diary").innerHTML = "<i>ao vivo: o diário aparece ao fim do dia</i>";
    },
    onTick: (msg) => {
      if (!(replay instanceof LiveReplay)) return;
      replay.push(msg);
      $<HTMLInputElement>("scrub").max = String(replay.manifest.ticks - 1);
      if (liveFollow) { tick = replay.manifest.ticks - 1; draw(); }
      if (msg.events?.length) buildEventMarkers();
    },
    onChanges: (changes) => {
      for (const c of changes) {
        if (c.type === "patch") world?.addPatch(c.x, c.y, c.r, c.kind);
        else if (c.type === "sphere") { world?.addSphere(c.x, c.y, c.r, c.surface); if (replay) replay.manifest.n_spheres = Math.max(replay.manifest.n_spheres, 0); }
        else if (c.type === "robot") world?.addRobot(c);
      }
    },
    onEnd: (msg) => { if (msg.diary) $("diary").innerHTML = "<pre>" + String(msg.diary).replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch] as string)) + "</pre>"; },
  });
  live.connect();
}

async function open(dir: string) {
  if (live) { live.close(); live = null; $("livestatus").textContent = ""; document.body.classList.remove("live"); }
  $("load").style.display = "flex";
  $<HTMLSelectElement>("run").value = dir;      // o seletor mostra o que esta aberto de fato
  brainDir = dir; brainFly = -1;
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
  const diary = $<HTMLDivElement>("diary");
  diary.innerHTML = replay.manifest.diary ? "<pre>" + replay.manifest.diary.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] as string)) + "</pre>" : "<i>sem diário neste replay</i>";
  $("load").style.display = "none";
  draw();
}

function buildFlyPanel() {
  const div = $("flies");
  div.innerHTML = "";
  replay!.manifest.flies.forEach((f, i) => {
    const b = document.createElement("button");
    const md = replay ? mood(replay, Math.max(0, Math.min(replay.manifest.ticks - 1, Math.floor(tick))), i) : null;
    b.innerHTML = `<span class="dot" style="background:${f.color}"></span>${f.name} <span style="color:#8b98a5">${f.sex === "male" ? "♂" : "♀"}</span> ${md ? md.emoji : ""}`;
    b.onclick = () => { if (selected === i) dossierOn = !dossierOn; else dossierOn = true; selected = i; buildFlyPanel(); draw(); };
    if (i === selected) b.classList.add("active");
    div.appendChild(b);
  });
}

const EVENT_COLORS: Record<string, string> = { encontro: "#f4a261", salto: "#e63946", presa_na_agua: "#4cc9f0", resgate_da_agua: "#7ee787", esfera_empurrada: "#ffd166", estado: "#ffffff22",
  entrou_no_lab: "#c77dff", afundou: "#4cc9f0", captura: "#ff3b3b", soltura: "#adb5bd", robo_persegue: "#ff7b54", segredo_quase: "#ffd166", segredo_disparado: "#00ff88", fuga: "#ffffff" };
function buildEventMarkers() {
  const div = $("events");
  div.innerHTML = "";
  const T = replay!.manifest.seconds;
  for (const e of replay!.events) {
    if (e.kind === "estado") continue;
    if (e.kind === "robo_persegue" && Math.random() > 0.3) continue;   // muitos: amostra
    const s = document.createElement("span");
    s.style.left = `${(e.t / T) * 100}%`;
    s.style.background = EVENT_COLORS[e.kind] ?? "#fff";
    if (e.kind === "segredo_disparado" || e.kind === "fuga") { s.style.height = "22px"; s.style.width = "4px"; }
    s.title = `${e.t.toFixed(1)} s ${e.kind}${e.secret ? " " + e.secret : ""} ${e.flies.join(", ")}`;
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
  if (replay.rowLen) {
    world.robots.forEach((rm, i) => { const r = replay!.robot(k, i); rm.update(r.x, r.y, r.lab, r.state, world!.height, t); });
    const ls = replay.labState(k);
    world.setLab(ls.door, ls.hatch, ls.genOff, ls.elevator);
  }
  let anyUnder = false;
  let anyBetting = false;
  const sel = $<HTMLDivElement>("hudbody");
  let selPos = new THREE.Vector3();
  world.flies.forEach((fm, i) => {
    const x = replay!.get(k, i, "x"), y = replay!.get(k, i, "y");
    const heading = replay!.get(k, i, "heading");
    const state = replay!.stateNames[replay!.get(k, i, "state")] ?? "?";
    const lvl = replay!.level(k, i);
    const pos = lvl === 1 ? new THREE.Vector3(x, -world!.labDepth, -y) : world!.toThree(x, y, 0);
    fm.group.visible = lvl !== 2;
    if (lvl === 1) anyUnder = true;
    if (state === "apostando") anyBetting = true;
    fm.update(pos, heading, state, t, Math.abs(replay!.get(k, i, "v")) > 0.05);
    const md = mood(replay!, k, i);
    const th = thoughts(replay!, k, i);
    fm.setBubble(md.emoji + (th.length ? " " + th.map((x) => x.emoji).join("") : ""));
    if (i === selected) {
      selPos = pos;
      const f = m.flies[i];
      const rates = ["MN9", "gf", "odn1", "dna01", "dna02", "mdn", "p1", "pip10"].map((p) => {
        const key = `rate_${p}_all`; return key in replay!.fi ? `${p} ${replay!.get(k, i, key).toFixed(1)}` : null;
      }).filter(Boolean).join(" · ");
      const lk = likes(replay!, k, i);
      sel.innerHTML = `<b style="color:${f.color}">${f.name}</b> ${f.sex === "male" ? "♂ macho" : "♀ fêmea"} — <span class="muted">${f.hud}</span><br>` +
        `<span style="font-size:18px">${md.emoji}</span> <b style="color:${md.color}">${md.word}</b> · pensa em: ${th.length ? th.map((x) => `${x.emoji} ${x.label}`).join(", ") : "nada (sensores em silêncio)"}<br>` +
        `estado: <b>${state}</b> · v ${replay!.get(k, i, "v").toFixed(2)} cm/s · fome ×${replay!.get(k, i, "hunger").toFixed(2)}` +
        (replay!.get(k, i, "ignited") > 0 ? ' · <b style="color:#e63946">CONVULSÃO</b>' : "") + "<br>" +
        `gosta de: ${lk.length ? lk.join(", ") : "ainda não se sabe"}<br>` +
        `<span class="muted">Hz: ${rates}</span><br>` +
        `<span class="muted">${m.brain_mode === "full" ? "cérebro completo" : "cérebro reduzido"} · luz ${(light * 100).toFixed(0)} % · dia ${m.day_index ?? 0}${lvl === 1 ? " · <b style=\"color:#c77dff\">NO LABORATÓRIO</b>" : lvl === 2 ? " · <b>FUGIU</b>" : ""}</span>`;
    }
  });
  world.setUnderground(anyUnder || camMode === "security");
  world.spinRoulette(anyBetting, t);
  if (camMode === "security") {
    const lab = m.world.lab; const [x0, y0, x1, y1] = lab.bounds;
    // canto sudeste do laboratorio, olhando em diagonal para o centro (camera de seguranca)
    camera.position.lerp(new THREE.Vector3(x1 - 2, -world.labDepth + 5, -y0 - 2), 0.1);
    controls.target.lerp(new THREE.Vector3((x0 + x1) / 2 - 4, -world.labDepth + 0.5, -(y0 + y1) / 2), 0.2);
  } else if (camMode === "follow") {
    // segue a mosca mantendo o deslocamento escolhido pelo usuario: orbita e zoom continuam livres
    if (!followPrev) { followPrev = selPos.clone(); camera.position.copy(selPos).add(new THREE.Vector3(-4, 3, 4)); }
    const delta = selPos.clone().sub(followPrev);
    camera.position.add(delta);
    controls.target.copy(selPos);
    followPrev = selPos.clone();
  } else if (camMode === "top") {
    camera.position.lerp(new THREE.Vector3(0.01, m.world.arena.radius_cm * 2.2, 0), 0.1);
    controls.target.lerp(new THREE.Vector3(0, 0, 0), 0.2);
  }
  if (k % 66 === 0) buildFlyPanel();
  $<HTMLInputElement>("scrub").value = String(k);
  if (dossierOn) drawDossier(k);
  $("dossier").style.display = dossierOn ? "block" : "none";
  if (brainOn || matrixOn) {
    if (brainFly !== selected) { brainFly = selected; brain.load(replay, brainDir, selected); }
    brain.update(replay.spikes(k, selected), m.dt_s);
    traces.draw(replay, selected, k);
    const bs = m.brain_samples?.find((b) => b.fly === selected);
    $("braininfo").textContent = bs ? `${m.flies[selected].name}: ${bs.n} somas de ${bs.n_total} neurônios (coordenadas do próprio conectoma) · ${replay.spikes(k, selected).length} disparos nesta janela` : "sem amostra neural neste replay";
  }
  $("clock").textContent = live ? `${t.toFixed(1).replace(".", ",")} s ao vivo` : `${t.toFixed(1).replace(".", ",")} s / ${Math.round(m.seconds)} s`;
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
  } else if (replay && camMode !== "orbit" && camMode !== "follow") {
    draw();   // cameras que interpolam precisam redesenhar mesmo em pausa
  }
  controls.update();
  if (world) renderer.render(world.scene, camera);
  if ((brainOn || matrixOn) && brain.points) {
    const w = brainCanvas.clientWidth, h = brainCanvas.clientHeight;
    if (brainCanvas.width !== w || brainCanvas.height !== h) { brainRenderer.setSize(w, h, false); brain.camera.aspect = w / h; brain.camera.updateProjectionMatrix(); }
    brainRenderer.render(brain.scene, brain.camera);
  }
}

function drawDossier(k: number) {
  if (!replay) return;
  const f = replay.manifest.flies[selected];
  const esc = (x: string) => x.replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch] as string));
  $("dossierbody").innerHTML =
    `<h3 style="color:${f.color}">${f.name} ${f.sex === "male" ? "♂" : "♀"} — dossiê</h3>` +
    `<div class="bars">${esc(needsBars(replay, k, selected))}</div>` +
    `<h3>Traços e gostos</h3><ul>${traits(replay, k, selected).map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` +
    `<h3>Relações</h3><ul>${relationLines(replay, k, selected).map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` +
    `<h3>Últimos acontecimentos</h3><ul class="log">${recentLog(replay, k, selected).map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`;
}

function godCommand(cmd: string, el?: HTMLElement) {
  if (!live || !replay) { $("livestatus").textContent = "🔴 o modo Deus só age ao vivo"; return; }
  const name = replay.manifest.flies[selected].name;
  const k = Math.max(0, Math.min(replay.manifest.ticks - 1, Math.floor(tick)));
  const x = replay.get(k, selected, "x"), y = replay.get(k, selected, "y");
  const payload: any = { cmd, fly: name };
  if (cmd === "teleport") { payload.x = 0; payload.y = 0; payload.level = "surface"; }
  if (cmd === "add_food" || cmd === "add_ball") { payload.x = x + 2; payload.y = y + 1; }
  if (cmd === "add_robot") payload.level = "surface";
  if (cmd === "set_need") { payload.need = el?.dataset.need ?? "romance"; payload.value = 1.0; }
  live.send(payload);
}

function setBrainUI() {
  brainCanvas.style.display = brainOn || matrixOn ? "block" : "none";
  $("brainpanel").style.display = brainOn || matrixOn ? "block" : "none";
  document.body.classList.toggle("matrix", matrixOn);
  if (replay) { brainFly = -1; draw(); }
}
$("brainbtn").onclick = () => { brainOn = !brainOn; if (brainOn) matrixOn = false; setBrainUI(); };
$("matrixbtn").onclick = () => { matrixOn = !matrixOn; if (matrixOn) brainOn = false; setBrainUI(); };
$("godbtn").onclick = () => { const g = $("god"); g.style.display = g.style.display === "block" ? "none" : "block"; };
document.querySelectorAll<HTMLButtonElement>("#god button[data-cmd]").forEach((b) => (b.onclick = () => godCommand(b.dataset.cmd!, b)));
document.querySelectorAll<HTMLInputElement>("#god input[data-mute]").forEach((c) => (c.onchange = () => live?.send({ cmd: "mute", channel: c.dataset.mute, on: c.checked })));
$<HTMLInputElement>("scrub").addEventListener("input", () => { liveFollow = false; });
$("recbtn").onclick = () => {
  if (recorder) { recorder.stop(); recorder = null; $("recbtn").textContent = "⏺ vídeo"; return; }
  const stream = (renderer.domElement as HTMLCanvasElement).captureStream(30);
  const chunks: Blob[] = [];
  recorder = new MediaRecorder(stream, { mimeType: "video/webm;codecs=vp9" });
  recorder.ondataavailable = (e) => chunks.push(e.data);
  recorder.onstop = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(chunks, { type: "video/webm" }));
    a.download = `matrix-das-moscas-${brainDir.replace("/", "_")}.webm`;
    a.click();
  };
  recorder.start(500);
  $("recbtn").textContent = "⏹ parar";
  if (!playing) $("play").click();
};

$("livebtn").onclick = () => { if (!live) openLive(); };
$("stopbtn").onclick = () => live?.send({ cmd: "stop" });
$("resetbtn").onclick = () => { live?.send({ cmd: "reset" }); liveFollow = true; };
$("nowbtn").onclick = () => { liveFollow = true; if (replay) { tick = replay.manifest.ticks - 1; draw(); } };
$("play").onclick = () => {
  if (live) {
    // ao vivo: ▶ comeca ou retoma o TEMPO da simulacao; ❚❚ pausa de verdade
    if (liveState === "idle") live.send({ cmd: "start" });
    else if (liveState === "running") live.send({ cmd: "pause" });
    else if (liveState === "paused") live.send({ cmd: "resume" });
    liveFollow = true;
    return;
  }
  playing = !playing; $("play").textContent = playing ? "❚❚" : "▶"; if (replay && tick >= replay.manifest.ticks - 1) tick = 0; };
$<HTMLSelectElement>("speed").onchange = (e) => (speed = +(e.target as HTMLSelectElement).value);
$<HTMLSelectElement>("cam").onchange = (e) => { camMode = (e.target as HTMLSelectElement).value; followPrev = null; };
$("diarybtn").onclick = () => { const d = $("diary"); d.style.display = d.style.display === "block" ? "none" : "block"; };
addEventListener("keydown", (e) => { if (e.code === "Space") { e.preventDefault(); $("play").click(); } });

(window as any).__dbg = { get world() { return world; }, get replay() { return replay; }, camera, controls, get camMode() { return camMode; } };
boot();
loop();
