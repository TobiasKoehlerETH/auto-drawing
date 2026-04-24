import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";

import puppeteer from "puppeteer";

const appUrl = process.env.APP_URL ?? "http://127.0.0.1:5173";
const outputDir = path.resolve(process.cwd(), ".generated");
const screenshotPath = path.join(outputDir, "smoke-view-layout.png");
const executablePath = findBrowserExecutable();
const toleranceMm = 0.05;

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

  let previewId = await readPreviewId(page);
  await uploadFixture(page, path.resolve(process.cwd(), "public", "fixtures", "cube-30.step"));
  await waitForIdle(page);
  await waitForPreviewIdChange(page, previewId);
  await waitForCanvasSelector(page, "[data-hitbox-for='view-front']", 45000);

  const cubeInitial = await readViewPositions(page);
  await dragHitbox(page, "view-front", 120, 60);
  await waitForIdle(page);
  const cubeMoved = await waitForViewPositionChange(page, cubeInitial, "view-front", "x");

  assertMoved(cubeInitial, cubeMoved, "view-front", "x");
  assertMoved(cubeInitial, cubeMoved, "view-front", "y");
  assertMoved(cubeInitial, cubeMoved, "view-right", "x");
  assertMoved(cubeInitial, cubeMoved, "view-right", "y");
  assertMoved(cubeInitial, cubeMoved, "view-top", "x");
  assertMoved(cubeInitial, cubeMoved, "view-top", "y");

  const rightInitial = cubeMoved;
  await dragHitbox(page, "view-right", 90, 65);
  await waitForIdle(page);
  const rightMoved = await waitForViewPositionChange(page, rightInitial, "view-right", "x");
  assertMoved(rightInitial, rightMoved, "view-right", "x");
  assertUnchanged(rightInitial, rightMoved, "view-right", "y");

  previewId = await readPreviewId(page);
  await uploadFixture(page, path.resolve(process.cwd(), "public", "fixtures", "hole-pattern.step"));
  await waitForIdle(page);
  await waitForPreviewIdChange(page, previewId);
  await waitForCanvasSelector(page, "[data-hitbox-for='view-front']", 45000);

  const plateInitial = await readViewPositions(page);
  await dragHitbox(page, "view-front", 80, 70);
  await waitForIdle(page);
  const frontMoved = await waitForViewPositionChange(page, plateInitial, "view-front", "y");
  assertUnchanged(plateInitial, frontMoved, "view-front", "x");
  assertMoved(plateInitial, frontMoved, "view-front", "y");

  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(
    JSON.stringify(
      {
        appUrl,
        screenshotPath,
        cubeInitial,
        cubeMoved,
        rightMoved,
        plateInitial,
        frontMoved,
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

async function waitForPreviewIdChange(page, previousPreviewId) {
  await page.waitForFunction(
    (previous) => {
      const current = document.querySelector("[data-preview-id]")?.getAttribute("data-preview-id") ?? "";
      return current.length > 0 && current !== previous;
    },
    { timeout: 45000 },
    previousPreviewId ?? "",
  );
}

async function waitForViewPositionChange(page, baseline, viewId, axis) {
  await page.waitForFunction(
    ([previous, targetViewId, targetAxis, tolerance]) => {
      const positions = Object.fromEntries(
        Array.from(document.querySelectorAll("[data-hitbox-for]")).map((node) => [
          node.getAttribute("data-hitbox-for"),
          {
            kind: node.getAttribute("data-view-kind"),
            x: Number.parseFloat(node.getAttribute("data-view-x-mm") ?? "NaN"),
            y: Number.parseFloat(node.getAttribute("data-view-y-mm") ?? "NaN"),
          },
        ]),
      );
      return Math.abs((positions[targetViewId]?.[targetAxis] ?? 0) - previous[targetViewId][targetAxis]) > tolerance;
    },
    { timeout: 15000 },
    [baseline, viewId, axis, toleranceMm],
  );
  return readViewPositions(page);
}

async function readViewPositions(page) {
  return page.evaluate(() =>
    Object.fromEntries(
      Array.from(document.querySelectorAll("[data-hitbox-for]")).map((node) => [
        node.getAttribute("data-hitbox-for"),
        {
          kind: node.getAttribute("data-view-kind"),
          x: Number.parseFloat(node.getAttribute("data-view-x-mm") ?? "NaN"),
          y: Number.parseFloat(node.getAttribute("data-view-y-mm") ?? "NaN"),
        },
      ]),
    ),
  );
}

async function readPreviewId(page) {
  return page
    .$eval("[data-preview-id]", (node) => node.getAttribute("data-preview-id") ?? "")
    .catch(() => "");
}

async function getInsetPoint(page, selector, inset = 16) {
  return page.$eval(selector, (node, targetInset) => {
    const rect = node.getBoundingClientRect();
    const insetPx = Math.min(targetInset, rect.width / 3, rect.height / 3);
    return {
      x: rect.left + insetPx,
      y: rect.top + insetPx,
    };
  }, inset);
}

function assertMoved(before, after, viewId, axis) {
  const delta = Math.abs(after[viewId][axis] - before[viewId][axis]);
  if (delta <= toleranceMm) {
    throw new Error(`${viewId} ${axis} did not move: ${JSON.stringify({ before: before[viewId], after: after[viewId] })}`);
  }
}

function assertUnchanged(before, after, viewId, axis) {
  const delta = Math.abs(after[viewId][axis] - before[viewId][axis]);
  if (delta > toleranceMm) {
    throw new Error(`${viewId} ${axis} changed unexpectedly: ${JSON.stringify({ before: before[viewId], after: after[viewId] })}`);
  }
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
