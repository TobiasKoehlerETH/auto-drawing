#!/usr/bin/env node
// Copies the opencascade.js WASM payload into public/ so Vite serves it as a
// static asset. Runs on postinstall so the file stays in sync with the
// installed package version.
import { copyFileSync, existsSync, mkdirSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../node_modules/opencascade.js/dist/opencascade.wasm.wasm");
const dst = resolve(here, "../public/opencascade.wasm");

if (!existsSync(src)) {
  console.warn(`[copy-occ-wasm] source missing: ${src} — skipping.`);
  process.exit(0);
}

mkdirSync(dirname(dst), { recursive: true });

if (existsSync(dst) && statSync(dst).size === statSync(src).size) {
  // Same size → assume already in sync. Avoids re-copying 60+ MB on every install.
  process.exit(0);
}

copyFileSync(src, dst);
const mb = (statSync(dst).size / (1024 * 1024)).toFixed(1);
console.log(`[copy-occ-wasm] ${mb} MB → public/opencascade.wasm`);
