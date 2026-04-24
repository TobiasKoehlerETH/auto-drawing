import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";

import puppeteer from "puppeteer";

const appUrl = process.env.APP_URL ?? "http://127.0.0.1:5173";
const outputDir = path.resolve(process.cwd(), ".generated", "ui-screenshots");
const executablePath = findBrowserExecutable();

const captures = [
  { name: "empty-desktop", viewport: { width: 1600, height: 1100 }, mode: "empty" },
  { name: "autoload-desktop", viewport: { width: 1600, height: 1100 }, mode: "autoload" },
  { name: "upload-fixture-desktop", viewport: { width: 1600, height: 1100 }, mode: "upload" },
  { name: "autoload-tablet", viewport: { width: 900, height: 900 }, mode: "autoload" },
  { name: "autoload-mobile", viewport: { width: 390, height: 844 }, mode: "autoload" },
];

await fs.mkdir(outputDir, { recursive: true });

const browser = await puppeteer.launch({
  headless: true,
  defaultViewport: captures[0].viewport,
  executablePath,
});

try {
  const page = await browser.newPage();
  const results = [];

  for (const capture of captures) {
    await page.setViewport(capture.viewport);

    if (capture.mode === "autoload") {
      await page.goto(`${appUrl}/?autoload=sample&qa=${capture.name}`, { waitUntil: "networkidle2" });
      await waitForPreview(page);
    } else {
      await page.goto(`${appUrl}/?qa=${capture.name}`, { waitUntil: "networkidle2" });
      if (capture.mode === "upload") {
        await uploadFixture(page, path.resolve(process.cwd(), "public", "fixtures", "cube-30.step"));
        await waitForPreview(page);
      } else {
        await waitForIdle(page);
      }
    }

    await page.evaluate(() => document.fonts?.ready);
    await page.waitForFunction(() => !document.querySelector(".animate-spin"), { timeout: 45000 }).catch(() => {});
    const screenshotPath = path.join(outputDir, `${capture.name}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    results.push({
      name: capture.name,
      viewport: capture.viewport,
      screenshotPath,
      previewId: await readPreviewId(page),
      bodySize: await page.evaluate(() => ({ width: document.body.scrollWidth, height: document.body.scrollHeight })),
    });
  }

  console.log(JSON.stringify({ appUrl, outputDir, results }, null, 2));
} finally {
  await browser.close();
}

async function waitForIdle(page) {
  await page.waitForFunction(() => !document.querySelector(".animate-spin"), { timeout: 45000 }).catch(() => {});
}

async function waitForPreview(page) {
  await page.waitForFunction(() => !!document.querySelector("[data-preview-id]"), { timeout: 60000 });
  await waitForIdle(page);
}

async function uploadFixture(page, fixturePath) {
  const input = await page.$('input[type="file"]');
  if (!input) {
    throw new Error("Unable to find file input");
  }
  await input.uploadFile(fixturePath);
}

async function readPreviewId(page) {
  return page
    .$eval("[data-preview-id]", (node) => node.getAttribute("data-preview-id") ?? "")
    .catch(() => "");
}

function findBrowserExecutable() {
  const candidates = [
    process.env.PUPPETEER_EXECUTABLE_PATH,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ].filter(Boolean);

  const match = candidates.find((candidate) => fsSync.existsSync(candidate));
  if (!match) {
    throw new Error("No local Chrome or Edge executable was found for the screenshot QA run.");
  }
  return match;
}
