/**
 * Capture PNGs for web/public/user-manual/images/
 *
 * Uses dark color scheme so `prefers-color-scheme: dark` (see globals.css) and
 * native form controls match the app’s dark UI — headless Chromium defaults to light.
 *
 *   PYTHONPATH=. uvicorn api.main:app --host 127.0.0.1 --port 8000
 *   cd web && npm run dev   # note the printed port if not 3000
 *   MANUAL_BASE_URL=http://127.0.0.1:3000 MANUAL_API_URL=http://127.0.0.1:8000 node scripts/capture-manual-ui.cjs
 */
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const out = path.join(__dirname, "../public/user-manual/images");
const base = process.env.MANUAL_BASE_URL || "http://127.0.0.1:3000";
const apiBase = process.env.MANUAL_API_URL || "http://127.0.0.1:8000";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

fs.mkdirSync(out, { recursive: true });

(async () => {
  const email = `manual-${Date.now()}@local.test`;
  const reg = await fetch(`${apiBase}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: "testpass12" }),
  });
  if (!reg.ok) {
    const t = await reg.text();
    throw new Error(`Register failed: ${reg.status} ${t}`);
  }
  const { access_token: token } = await reg.json();

  const browser = await chromium.launch({
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  const context = await browser.newContext({
    colorScheme: "dark",
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  /** Ensure each navigation picks up dark media + native widget styling */
  async function prepDarkUi() {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.evaluate(() => {
      document.documentElement.style.colorScheme = "dark";
      document.documentElement.classList.add("dark");
    });
  }

  async function cap(route, file) {
    await page.goto(base + route, { waitUntil: "domcontentloaded", timeout: 90000 });
    await prepDarkUi();
    await sleep(1200);
    await page.screenshot({ path: path.join(out, file) });
  }

  await cap("/login", "ui-login.png");
  await cap("/register", "ui-register.png");

  await page.goto(base + "/login", { waitUntil: "domcontentloaded", timeout: 90000 });
  await prepDarkUi();
  await page.evaluate(
    (t) => {
      localStorage.setItem("ol_token", t);
    },
    token
  );
  await page.goto(base + "/dashboard", { waitUntil: "networkidle", timeout: 90000 });
  await prepDarkUi();
  await sleep(1000);
  await page.screenshot({ path: path.join(out, "ui-dashboard.png") });

  await cap("/dashboard/research", "ui-research.png");
  await cap("/dashboard/volatility", "ui-volatility.png");
  await cap("/dashboard/settings", "ui-settings.png");
  await cap("/dashboard/data", "ui-data.png");
  await cap("/dashboard/economic", "ui-economic.png");

  await browser.close();
  console.log("Wrote screenshots to", out);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
