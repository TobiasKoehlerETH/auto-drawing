#!/usr/bin/env node
// Copies runtime JS/WASM payloads into public/ so Vite can serve them as
// static assets in both dev and production builds.
import { copyFileSync, existsSync, mkdirSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const copies = [
  {
    src: resolve(here, "../node_modules/opencascade.js/dist/opencascade.wasm.wasm"),
    dst: resolve(here, "../public/opencascade.wasm"),
    label: "opencascade.js wasm",
  },
  {
    src: resolve(here, "../node_modules/occt-import-js/dist/occt-import-js.js"),
    dst: resolve(here, "../public/occt-import-js.js"),
    label: "occt-import-js loader",
  },
  {
    src: resolve(here, "../node_modules/occt-import-js/dist/occt-import-js.wasm"),
    dst: resolve(here, "../public/occt-import-js.wasm"),
    label: "occt-import-js wasm",
  },
];

for (const { src, dst, label } of copies) {
  if (!existsSync(src)) {
    console.warn(`[copy-occ-wasm] missing ${label}: ${src} - skipping.`);
    continue;
  }

  mkdirSync(dirname(dst), { recursive: true });

  if (existsSync(dst) && statSync(dst).size === statSync(src).size) {
    continue;
  }

  copyFileSync(src, dst);
  const mb = (statSync(dst).size / (1024 * 1024)).toFixed(1);
  console.log(`[copy-occ-wasm] ${label}: ${mb} MB -> ${dst}`);
}
