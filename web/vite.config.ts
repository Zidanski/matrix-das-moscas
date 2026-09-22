import { defineConfig } from "vite";
import { existsSync, readFileSync, statSync, readdirSync } from "node:fs";
import { join, resolve, extname } from "node:path";
import { spawn, execSync, type ChildProcess } from "node:child_process";

// Serve ../runs em /runs (replays gravados pelo simulador; fora do git).
const RUNS = resolve(__dirname, "..", "runs");
const TYPES: Record<string, string> = { ".json": "application/json", ".bin": "application/octet-stream" };

let liveProc: ChildProcess | null = null;
function livePlugin() {
  return {
    name: "live-server",
    configureServer(server: any) {
      if (process.env.LIVE === "0" || liveProc) return;
      // um servidor antigo ainda na porta (dev server anterior encerrado sem matar a arvore) ficaria com codigo velho:
      // derruba-o antes de subir o novo
      const freePort = () => {
        try {
          if (process.platform === "win32") execSync(`powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"`, { stdio: "ignore" });
          else execSync("lsof -ti tcp:8765 | xargs -r kill", { stdio: "ignore", shell: "/bin/sh" });
        } catch {}
      };
      freePort();
      // `uv run matrix live` fica esperando o 'start' do navegador; morre com o dev server
      liveProc = spawn("uv", ["run", "matrix", "live", "--port", "8765"], { cwd: resolve(__dirname, ".."), stdio: "inherit", shell: true });
      liveProc.on("exit", () => (liveProc = null));
      const kill = () => {
        // shell:true -> kill() mataria so o cmd.exe; mata a arvore inteira (uv -> matrix.exe -> python)
        try { if (process.platform === "win32" && liveProc?.pid) execSync(`taskkill /PID ${liveProc.pid} /T /F`, { stdio: "ignore" }); else liveProc?.kill(); } catch {}
        freePort();
      };
      server.httpServer?.once("close", kill);
      process.once("exit", kill);
      process.once("SIGINT", () => { kill(); process.exit(); });
    },
  };
}

function runsPlugin() {
  return {
    name: "serve-runs",
    configureServer(server: any) {
      server.middlewares.use((req: any, res: any, next: any) => {
        if (!req.url?.startsWith("/runs")) return next();
        const rel = decodeURIComponent(req.url.split("?")[0].slice("/runs".length)).replace(/^\/+/, "");
        const p = join(RUNS, rel);
        if (!existsSync(p)) { res.statusCode = 404; return res.end("not found"); }
        if (statSync(p).isDirectory()) {
          res.setHeader("Content-Type", "application/json");
          return res.end(JSON.stringify(readdirSync(p)));
        }
        res.setHeader("Content-Type", TYPES[extname(p)] ?? "application/octet-stream");
        res.end(readFileSync(p));
      });
    },
  };
}

export default defineConfig({ plugins: [runsPlugin(), livePlugin()], server: { port: 5173 } });
