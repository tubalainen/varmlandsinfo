// Skärmdumpar till README (docs/screenshots/). Kör mot en app med riktig evenemangsdata:
//
//   npm i -g playwright            # en gång
//   node tools/readme-screenshots.mjs [http://localhost:8080]
//
// Fråga AI-bilden använder en sökfråga, så den fungerar utan Ollama. Status-raden visar modellnamnet
// om Ollama går att nå. Kontrollera alltid bilderna innan de checkas in: inga privata adresser får synas.
//
// Bakom en proxy som bryter upp HTTPS (t.ex. i en molnmiljö) laddas evenemangsbilderna via
// SCREENSHOT_PROXY=http://värd:port.

import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const base = (process.argv[2] || "http://localhost:8080").replace(/\/$/, "");
const out = new URL("../docs/screenshots/", import.meta.url).pathname;
mkdirSync(out, { recursive: true });

const proxy = process.env.SCREENSHOT_PROXY;
const browser = await chromium.launch(proxy ? { proxy: { server: proxy, bypass: new URL(base).hostname } } : {});

async function page(name, { scheme = "light", width = 1400, height = 900, route, prepare }) {
  const ctx = await browser.newContext({ colorScheme: scheme, viewport: { width, height }, ignoreHTTPSErrors: !!proxy,
                                         locale: "sv-SE", timezoneId: "Europe/Stockholm" });
  const p = await ctx.newPage();
  // Bilderna som syns ska vara laddade. Misslyckas någon laddas sidan om (högst tre försök).
  const loaded = () => p.waitForFunction(() => [...document.images]
    .filter((i) => i.getBoundingClientRect().top < innerHeight && i.getBoundingClientRect().bottom > 0)
    .every((i) => i.complete && i.naturalWidth > 0), null, { timeout: 15000 }).then(() => true, () => false);
  for (let attempt = 1; attempt <= 3; attempt++) {
    await p.goto(`${base}/#/${route}`);
    await p.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});
    if (prepare) await prepare(p);
    if (await loaded()) break;
    if (attempt === 3) console.warn(`${name}: alla bilder laddades inte`);
    else await p.reload();
  }
  await p.waitForTimeout(300);
  await p.screenshot({ path: `${out}${name}.jpg`, type: "jpeg", quality: 82 });
  await ctx.close();
  console.log(`${out}${name}.jpg`);
}

await page("lista", { route: "lista", prepare: (p) => p.waitForSelector(".card") });
await page("kalender", { scheme: "dark", route: "kalender", prepare: (p) => p.waitForSelector(".cal-ev") });
await page("fraga-ai", {
  route: "fraga",
  prepare: async (p) => {
    await p.fill("#chat-input", "När spelar Färjestad nästa gång?");
    await p.keyboard.press("Enter");
    await p.waitForSelector(".msg.assistant .cached-note");
  },
});
await page("mobil", { scheme: "dark", width: 390, height: 844, route: "lista", prepare: (p) => p.waitForSelector(".card") });

await browser.close();
