// Kontrastkontroll av webbgränssnittet i ljust och mörkt läge (WCAG AA).
//
// Kör mot en körande app:   node tools/contrast-check.mjs [http://localhost:8080]
// Kräver Playwright (npm i -D playwright). Avslutas med felkod 1 om något textelement har för låg kontrast.
// Skärmdumpar sparas i tools/screenshots/ (ingår inte i git).

import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const BASE = process.argv[2] || "http://localhost:8080";
const OUT = new URL("./screenshots/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

// Körs i sidan: mät kontrast för alla synliga textelement
function audit() {
  const parse = (c) => {
    if (!c || c === "transparent") return [0, 0, 0, 0];
    let m = c.match(/rgba?\(([^)]+)\)/);
    if (m) {
      const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
      return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
    }
    m = c.match(/color\(srgb ([^)]+)\)/);
    if (m) {
      const p = m[1].split(/[\s/]+/).filter(Boolean).map(Number);
      return [p[0] * 255, p[1] * 255, p[2] * 255, p.length > 3 ? p[3] : 1];
    }
    return null;
  };
  const over = (top, bottom) => {
    const a = top[3];
    return [0, 1, 2].map((i) => top[i] * a + bottom[i] * (1 - a)).concat(1);
  };
  const lum = (c) => {
    const [r, g, b] = c.slice(0, 3).map((v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const ratio = (a, b) => {
    const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  };
  const background = (el) => {
    const layers = [];
    let opacity = 1;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      opacity *= parseFloat(cs.opacity);
      const bg = parse(cs.backgroundColor);
      if (bg && bg[3] > 0) layers.push(bg);
      if (bg && bg[3] >= 1) break;
      if (n.tagName === "DIALOG" && n.open) break;
    }
    let base = parse(getComputedStyle(document.documentElement).backgroundColor);
    if (!base || base[3] === 0) base = parse(getComputedStyle(document.body).backgroundColor);
    for (const l of layers.reverse()) base = over(l, base);
    return { bg: base, opacity };
  };
  const label = (el) => {
    const cls = typeof el.className === "string" && el.className ? "." + el.className.trim().split(/\s+/).join(".") : "";
    const parent = el.parentElement;
    const pcls = parent && typeof parent.className === "string" && parent.className
      ? parent.className.trim().split(/\s+/)[0] : parent?.tagName.toLowerCase();
    return `${pcls} > ${el.tagName.toLowerCase()}${cls}`;
  };

  const failures = [];
  const seen = new Set();
  let checked = 0;
  for (const el of document.querySelectorAll("body *")) {
    if (["SCRIPT", "STYLE", "OPTION"].includes(el.tagName)) continue;
    const text = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join("").trim();
    if (!text) continue;
    const rect = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (!rect.width || !rect.height || cs.visibility === "hidden" || cs.display === "none") continue;
    if (el.closest("[hidden]") || el.matches(":disabled") || el.closest("button:disabled")) continue;
    const dlg = el.closest("dialog");
    if (dlg && !dlg.open) continue;
    const { bg, opacity } = background(el);
    const fg = parse(cs.color);
    if (!fg || !bg) continue;
    const eff = over([fg[0], fg[1], fg[2], fg[3] * opacity], bg);
    const r = ratio(eff, bg);
    const size = parseFloat(cs.fontSize);
    const bold = parseInt(cs.fontWeight, 10) >= 700;
    const large = size >= 24 || (bold && size >= 18.66);
    const need = large ? 3 : 4.5;
    checked++;
    if (r < need) {
      const key = label(el) + "|" + cs.color + "|" + bg.map(Math.round).join(",");
      if (seen.has(key)) continue;
      seen.add(key);
      failures.push({ where: label(el), text: text.slice(0, 40), ratio: +r.toFixed(2), need,
                      fg: cs.color, bg: `rgb(${bg.slice(0, 3).map(Math.round).join(", ")})` });
    }
  }
  return { checked, failures };
}

const browser = await chromium.launch({ args: ["--ignore-certificate-errors"] });
let total = 0;
for (const scheme of ["light", "dark"]) {
  const page = await browser.newPage({ colorScheme: scheme, ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } });
  const run = async (name, prepare) => {
    await prepare(page);
    await page.waitForTimeout(400);
    const { checked, failures } = await page.evaluate(audit);
    await page.screenshot({ path: `${OUT}${scheme}-${name}.png` });
    total += failures.length;
    console.log(`${scheme.padEnd(5)} ${name.padEnd(9)} ${checked} textelement, ${failures.length} med för låg kontrast`);
    for (const f of failures) console.log(`   ${f.ratio}:1 (krav ${f.need}:1)  ${f.where}  "${f.text}"  ${f.fg} på ${f.bg}`);
  };
  await page.goto(BASE);
  await page.evaluate(() => { try { localStorage.clear(); } catch {} });
  await page.goto(`${BASE}/#/lista`);
  await page.waitForSelector(".card");

  await run("lista", async (p) => { await p.click(".chip >> nth=0"); });   // med ett valt kategorifilter
  await run("kalender", async (p) => { await p.goto(`${BASE}/#/kalender`); await p.waitForSelector(".cal-grid"); });
  await run("dag", async (p) => { await p.click(".cal-day.today .cal-num"); await p.waitForSelector("#daydialog[open]"); });
  await run("fraga", async (p) => { await p.keyboard.press("Escape"); await p.goto(`${BASE}/#/fraga`); await p.waitForSelector(".suggestion"); });
  await run("chatt", async (p) => {
    await p.fill("#chat-input", "Vad händer i helgen?");
    await p.press("#chat-input", "Enter");
    await p.waitForTimeout(1500);
  });
  await run("om", async (p) => { await p.goto(`${BASE}/#/om`); await p.waitForSelector(".src-table"); });
  await run("mobil", async (p) => {
    await p.setViewportSize({ width: 390, height: 844 });
    await p.goto(`${BASE}/#/lista`); await p.waitForSelector(".card");
    await p.click("#nav-open"); await p.waitForTimeout(300);
  });
  await page.close();
}
await browser.close();
console.log(total ? `\n${total} problem hittades.` : "\nInga kontrastproblem.");
process.exit(total ? 1 : 0);
