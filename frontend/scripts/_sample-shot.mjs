import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer";

const appUrl = "http://127.0.0.1:5173";
const outDir = path.resolve(process.cwd(), "..", ".generated");
await fs.mkdir(outDir, { recursive: true });

function findBrowser() {
  const candidates = [
    process.env.PUPPETEER_EXECUTABLE_PATH,
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  ].filter(Boolean);
  for (const p of candidates) {
    try { fsSync.accessSync(p); return p; } catch {}
  }
  return undefined;
}

const browser = await puppeteer.launch({
  headless: true,
  defaultViewport: { width: 1800, height: 1300 },
  executablePath: findBrowser(),
});

try {
  const page = await browser.newPage();
  const fixturePath = path.resolve(process.cwd(), "public", "fixtures", "sample.step");
  await page.goto(`${appUrl}/?qa=sample`, { waitUntil: "networkidle2" });
  const input = await page.waitForSelector('input[type=file]', { timeout: 10000 });
  await input.uploadFile(fixturePath);
  await page.waitForFunction(() => document.querySelectorAll("canvas").length > 0, { timeout: 30000 });
  await new Promise(r => setTimeout(r, 5000));
  await page.waitForFunction(() => !document.querySelector(".animate-spin"), { timeout: 45000 }).catch(() => {});
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: path.join(outDir, "sample-sheet.png"), fullPage: true });
  console.log("ok " + path.join(outDir, "sample-sheet.png"));
} finally {
  await browser.close();
}
