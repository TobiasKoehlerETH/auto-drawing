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

  await scaleSelectedView(page, 40, 36);
  await waitForIdle(page);
  const scaledFront = await waitForMetricChange(page, movedFront, "scale");

  await clickButtonByAriaLabel(page, "Select top view");
  await waitForSelectedView(page, "view-top");
  const initialTop = await readViewMetrics(page);
  await dragHitbox(page, "view-top", -80, 45);
  await waitForIdle(page);
  const movedTop = await waitForMetricChange(page, initialTop, "x");

  const initialWidthDimension = await readDimensionPlacement(page, "dim-front-width");
  await dragElement(page, "[data-dimension-id='dim-front-width']", 0, 48);
  await waitForIdle(page);
  const movedWidthDimension = await waitForDimensionPlacementChange(page, "dim-front-width", initialWidthDimension, "y");

  if (movedFront.x <= initialFront.x || movedFront.y <= initialFront.y) {
    throw new Error(`Front view did not move as expected: ${JSON.stringify({ initialFront, movedFront })}`);
  }
  if (scaledFront.scale <= movedFront.scale) {
    throw new Error(`Front view did not scale up as expected: ${JSON.stringify({ movedFront, scaledFront })}`);
  }
  if (movedTop.x >= initialTop.x || movedTop.y <= initialTop.y) {
    throw new Error(`Top view did not move independently as expected: ${JSON.stringify({ initialTop, movedTop })}`);
  }
  if (movedWidthDimension.y <= initialWidthDimension.y) {
    throw new Error(`Front width dimension did not stay moved as expected: ${JSON.stringify({ initialWidthDimension, movedWidthDimension })}`);
  }

  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(
    JSON.stringify(
      {
        appUrl,
        screenshotPath,
        initialFront,
        movedFront,
        scaledFront,
        initialTop,
        movedTop,
        initialWidthDimension,
        movedWidthDimension,
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

async function dragElement(page, selector, deltaX, deltaY) {
  const box = await getCenter(page, selector);
  await page.mouse.move(box.x, box.y);
  await page.mouse.down();
  await page.mouse.move(box.x + deltaX, box.y + deltaY, { steps: 18 });
  await page.mouse.up();
}

async function scaleSelectedView(page, deltaX, deltaY) {
  await waitForCanvasSelector(page, "[data-resize-handle]");
  const handle = await getCenter(page, "[data-resize-handle]");
  await page.mouse.move(handle.x, handle.y);
  await page.mouse.down();
  await page.mouse.move(handle.x + deltaX, handle.y + deltaY, { steps: 18 });
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

async function waitForDimensionPlacementChange(page, dimensionId, baseline, metric) {
  await page.waitForFunction(
    ([targetId, previous, targetMetric]) => {
      const node = document.querySelector(`[data-dimension-id='${targetId}']`);
      if (!node) return false;
      const value = parseFloat(node.getAttribute(`data-dimension-${targetMetric}`) ?? "NaN");
      return Number.isFinite(value) && Math.abs(value - previous[targetMetric]) > 0.05;
    },
    { timeout: 15000 },
    [dimensionId, baseline, metric],
  );
  return readDimensionPlacement(page, dimensionId);
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

async function readDimensionPlacement(page, dimensionId) {
  return page.$eval(`[data-dimension-id='${dimensionId}']`, (node) => ({
    x: parseFloat(node.getAttribute("data-dimension-x") ?? "NaN"),
    y: parseFloat(node.getAttribute("data-dimension-y") ?? "NaN"),
  }));
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
