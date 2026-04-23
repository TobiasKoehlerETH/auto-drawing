import fs from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer";

const [htmlPath, outputPath] = process.argv.slice(2);

if (!htmlPath || !outputPath) {
  console.error("Usage: node export-pdf.mjs <htmlPath> <outputPath>");
  process.exit(1);
}
const html = await fs.readFile(htmlPath, "utf8");
const executablePath = resolveBrowser();

const browser = await puppeteer.launch({
  headless: true,
  executablePath
});

try {
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: "networkidle0" });
  await page.pdf({
    path: outputPath,
    printBackground: true,
    preferCSSPageSize: true
  });
} finally {
  await browser.close();
}

function resolveBrowser() {
  const candidates = [
    process.env.PUPPETEER_EXECUTABLE_PATH,
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
  ].filter(Boolean);

  for (const candidate of candidates) {
    try {
      const normalized = path.normalize(candidate);
      if (existsSync(normalized)) return normalized;
    } catch {
      // Ignore malformed candidates and continue.
    }
  }
  throw new Error("No supported Chromium browser executable was found for Puppeteer export.");
}
