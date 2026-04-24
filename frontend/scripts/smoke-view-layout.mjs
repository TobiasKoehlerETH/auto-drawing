import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";

import puppeteer from "puppeteer";

const appUrl = process.env.APP_URL ?? "http://127.0.0.1:5173";
const outputDir = path.resolve(process.cwd(), ".generated");
const screenshotPath = path.join(outputDir, "smoke-view-layout.png");
const executablePath = findBrowserExecutable();

await fs.mkdir(outputDir, { recursive: true });

const browser = await puppeteer.launch({
  headless: true,
  defaultViewport: { width: 1600, height: 1100 },
  executablePath,
});

try {
  const page = await browser.newPage();
  await page.goto(appUrl, { waitUntil: "networkidle2" });
  await waitForIdle(page);
  await uploadFixture(page, path.resolve(process.cwd(), "public", "fixtures", "cube-30.step"));
  await waitForIdle(page);
  await waitForCanvasSelector(page, "[data-hitbox-for='view-front']", 45000);

  await clickHitbox(page, "view-front");
  await waitForSelectedView(page, "view-front");

  const initialFront = await readViewMetrics(page);
  await dragHitbox(page, "view-front", 120, 60);
  await waitForIdle(page);
  const movedFront = await waitForMetricChange(page, initialFront, "x");

  await clickButtonByAriaLabel(page, "Select top view");
  await waitForSelectedView(page, "view-top");
  const initialTop = await readViewMetrics(page);
  await dragHitbox(page, "view-top", -80, 45);
  await waitForIdle(page);
  const movedTop = await waitForMetricChange(page, initialTop, "x");

  if (movedFront.x <= initialFront.x || movedFront.y <= initialFront.y) {
    throw new Error(`Front view did not move as expected: ${JSON.stringify({ initialFront, movedFront })}`);
  }
  if (Math.abs(initialFront.scale - 1.0) > 0.05 || Math.abs(movedFront.scale - 1.0) > 0.05) {
    throw new Error(`Front view did not stay at 1:1 scale as expected: ${JSON.stringify({ initialFront, movedFront })}`);
  }
  if (movedTop.x >= initialTop.x || movedTop.y <= initialTop.y) {
    throw new Error(`Top view did not move independently as expected: ${JSON.stringify({ initialTop, movedTop })}`);
  }

  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(
    JSON.stringify(
      {
        appUrl,
        screenshotPath,
        initialFront,
        movedFront,
        initialTop,
        movedTop,
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}

async function waitForIdle(page) {
  await page.waitForFunction(() => !document.querySelector(".animate-spin"), { timeout: 45000 });
}

async function uploadFixture(page, fixturePath) {
  const input = await page.$('input[type="file"]');
  if (!input) {
    throw new Error("Unable to find file input");
  }
  await input.uploadFile(fixturePath);
}

async function clickButtonByAriaLabel(page, ariaLabel) {
  const clicked = await page.evaluate((targetLabel) => {
    const button = Array.from(document.querySelectorAll("button")).find(
      (candidate) => candidate.getAttribute("aria-label") === targetLabel,
    );
    if (!button) return false;
    button.click();
    return true;
  }, ariaLabel);
  if (!clicked) {
    throw new Error(`Unable to find button with aria-label "${ariaLabel}"`);
  }
}

async function clickHitbox(page, targetId) {
  const point = await getInsetPoint(page, `[data-hitbox-for='${targetId}']`);
  await page.mouse.move(point.x, point.y);
  await page.mouse.click(point.x, point.y);
}

async function dragHitbox(page, targetId, deltaX, deltaY) {
  const point = await getInsetPoint(page, `[data-hitbox-for='${targetId}']`);
  await page.mouse.move(point.x, point.y);
  await page.mouse.down();
  await page.mouse.move(point.x + deltaX, point.y + deltaY, { steps: 18 });
  await page.mouse.up();
}

async function waitForCanvasSelector(page, selector, timeout = 15000) {
  await page.waitForFunction(
    (expectedSelector) => !!document.querySelector(expectedSelector),
    { timeout },
    selector,
  );
}

async function waitForSelectedView(page, targetId) {
  await page.waitForFunction(
    (expectedId) => document.querySelector("[data-selected-view-id]")?.getAttribute("data-selected-view-id") === expectedId,
    { timeout: 15000 },
    targetId,
  );
}

async function waitForMetricChange(page, baseline, metric) {
  await page.waitForFunction(
    ([previous, targetMetric]) => {
      const selected = document.querySelector("[data-selected-view-id]");
      if (!selected) return false;
      const metrics = Array.from(document.querySelectorAll("[data-view-metric]")).reduce((accumulator, node) => {
        const key = node.getAttribute("data-view-metric");
        const value = parseFloat(node.textContent?.replace(/[^0-9.-]+/g, " ")?.trim().split(/\s+/)[0] ?? "");
        if (key) {
          accumulator[key] = value;
        }
        return accumulator;
      }, {});
      return Math.abs((metrics[targetMetric] ?? 0) - previous[targetMetric]) > 0.05;
    },
    { timeout: 15000 },
    [baseline, metric],
  );
  return readViewMetrics(page);
}

async function readViewMetrics(page) {
  return page.evaluate(() => {
    const metrics = Array.from(document.querySelectorAll("[data-view-metric]")).reduce((accumulator, node) => {
      const key = node.getAttribute("data-view-metric");
      const value = parseFloat(node.textContent?.replace(/[^0-9.-]+/g, " ")?.trim().split(/\s+/)[0] ?? "");
      if (key) {
        accumulator[key] = value;
      }
      return accumulator;
    }, {});
    return {
      x: metrics.x ?? NaN,
      y: metrics.y ?? NaN,
      scale: metrics.scale ?? NaN,
    };
  });
}

async function getCenter(page, selector) {
  const box = await page.$eval(selector, (node) => {
    const rect = node.getBoundingClientRect();
    return {
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2,
    };
  });
  return box;
}

async function getInsetPoint(page, selector, inset = 16) {
  const box = await page.$eval(selector, (node, targetInset) => {
    const rect = node.getBoundingClientRect();
    const insetPx = Math.min(targetInset, rect.width / 3, rect.height / 3);
    return {
      x: rect.left + insetPx,
      y: rect.top + insetPx,
    };
  }, inset);
  return box;
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
    throw new Error("No local Chrome or Edge executable was found for the smoke test.");
  }
  return match;
}
