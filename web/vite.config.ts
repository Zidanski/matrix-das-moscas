import { defineConfig } from "vite";
import { existsSync, readFileSync, statSync, readdirSync } from "node:fs";
import { join, resolve, extname } from "node:path";

// Serve ../runs em /runs (replays gravados pelo simulador; fora do git).
const RUNS = resolve(__dirname, "..", "runs");
const TYPES: Record<string, string> = { ".json": "application/json", ".bin": "application/octet-stream" };

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

export default defineConfig({ plugins: [runsPlugin()], server: { port: 5173 } });
