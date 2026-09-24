"use strict";

const $ = (s) => document.querySelector(s);
function stored(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
}
function store(key, value) {
  try { localStorage.setItem(key, value); } catch { /* inte kritiskt */ }
}

const state = { events: [], today: null, cats: new Set(), view: stored("view", "list"), calMonth: null };

const fmtDay = new Intl.DateTimeFormat("sv-SE", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const fmtShort = new Intl.DateTimeFormat("sv-SE", { day: "numeric", month: "short" });
const parseDate = (d) => new Date(d + "T12:00:00");

function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "style") n.style.cssText = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null && c !== false) n.append(c);
  return n;
}

function dayLabel(iso) {
  const diff = Math.round((parseDate(iso) - parseDate(state.today)) / 86400000);
  const text = fmtDay.format(parseDate(iso));
  if (diff === 0) return ["Idag", text];
  if (diff === 1) return ["Imorgon", text];
  return [text.charAt(0).toUpperCase() + text.slice(1), ""];
}

function timeText(o) {
  if (!o.time_start) return "Tid ej angiven";
  return o.time_end ? `${o.time_start}–${o.time_end}` : `kl. ${o.time_start}`;
}

function openImage(img) {
  const d = $("#lightbox");
  d.querySelector("img").src = img.large;
  d.querySelector("img").alt = img.alt;
  d.querySelector("p").textContent = img.copyright ? `© ${img.copyright}` : "";
  d.showModal();
}

function fmtTime(iso) {
  return iso ? new Date(iso).toLocaleString("sv-SE", { dateStyle: "short", timeStyle: "short" }) : "–";
}

function showStatus(data) {
  let text;
  if (data.refreshing && !data.events.length) text = "Hämtar evenemang … (laddar om strax)";
  else if (!data.events.length && data.error) text = `Kunde inte hämta: ${data.error}`;
  else {
    text = `${data.events.length} aktuella evenemang · uppdaterad ${fmtTime(data.updated)}`;
    if (data.next_refresh) text += ` · nästa automatiska uppdatering ${fmtTime(data.next_refresh)}`;
    if (data.error) text += ` · senaste uppdateringen misslyckades: ${data.error}`;
    if (data.storage?.error) text += ` · ${data.storage.error}`;
  }
  $("#status").textContent = text;
  $("#version").textContent = data.version ? `v${data.version}` : "";
}

async function load() {
  try {
    const r = await fetch("/api/events");
    const data = await r.json();
    state.events = data.events;
    state.today = data.today;
    state.chat = data.chat;
    state.sources = data.sources;
    showStatus(data);
    if (!data.events.length) setTimeout(load, 5000);
    $("#from").min = state.today;
    buildFilters();
    render();
  } catch (e) {
    $("#status").textContent = "Fel vid hämtning: " + e;
    setTimeout(load, 10000);
  }
}

async function refreshEvents() {
  const btn = $("#refresh");
  btn.disabled = true;
  btn.textContent = "⟳ Uppdaterar …";
  $("#status").textContent = "Hämtar alla evenemang från Visit Värmland …";
  try {
    const r = await fetch("/api/refresh", { method: "POST" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const res = await r.json();
    await load();
    if (res.message) $("#status").textContent += ` · ${res.message}`;
  } catch (e) {
    $("#status").textContent = "Uppdateringen misslyckades: " + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "⟳ Uppdatera evenemang";
  }
}

function buildFilters() {
  const munis = [...new Set(state.events.map((e) => e.municipality).filter(Boolean))].sort((a, b) => a.localeCompare(b, "sv"));
  const sel = $("#municipality");
  const cur = sel.value;
  sel.replaceChildren(el("option", { value: "" }, "Alla kommuner"), ...munis.map((m) => el("option", { value: m }, m)));
  sel.value = cur;

  const srcSel = $("#source");
  const curSrc = srcSel.value;
  const srcNames = [...new Set(state.events.flatMap((e) => e.sources.map((x) => x.name)))].sort((a, b) => a.localeCompare(b, "sv"));
  srcSel.replaceChildren(el("option", { value: "" }, "Alla källor"), ...srcNames.map((m) => el("option", { value: m }, m)));
  srcSel.value = curSrc;
  $("#sources").replaceChildren(...Object.values(state.sources || {}).flatMap((x, i) => [
    i ? ", " : "",
    el("a", { href: x.homepage, target: "_blank", rel: "noopener",
      title: x.error || x.config_error || `Senast hämtad ${fmtTime(x.updated)}` }, x.title),
    x.enabled ? (x.error ? " (fel)" : ` (${x.count})`) : " (avstängd)",
  ]));

  const counts = new Map();
  for (const e of state.events) for (const c of e.categories) {
    const x = counts.get(c.title) || { ...c, n: 0 };
    x.n++; counts.set(c.title, x);
  }
  const box = $("#cats");
  box.replaceChildren(...[...counts.values()].sort((a, b) => b.n - a.n).map((c) =>
    el("button", {
      class: "chip", type: "button", title: c.description, style: `--c:${c.color}`,
      "aria-pressed": state.cats.has(c.title) ? "true" : "false",
      onclick: (ev) => {
        state.cats.has(c.title) ? state.cats.delete(c.title) : state.cats.add(c.title);
        ev.currentTarget.setAttribute("aria-pressed", state.cats.has(c.title));
        render();
      },
    }, `${c.icon} ${c.title}`, el("span", { class: "n" }, String(c.n)))));
}

function matches(e, q, muni) {
  if (muni && e.municipality !== muni) return false;
  const src = $("#source").value;
  if (src && !e.sources.some((s) => s.name === src)) return false;
  if (state.cats.size && !e.categories.some((c) => state.cats.has(c.title))) return false;
  if (q) {
    const hay = [e.title, e.summary, e.description, e.organizer, e.municipality, e.place?.title, e.place?.address,
      ...e.categories.map((c) => c.title)].join(" ").toLowerCase();
    return q.split(/\s+/).every((w) => hay.includes(w));
  }
  return true;
}

function render() {
  const cal = state.view === "calendar";
  document.body.classList.toggle("cal-mode", cal);
  $("#list").hidden = cal;
  $("#calendar").hidden = !cal;
  for (const b of document.querySelectorAll(".viewtoggle button")) b.setAttribute("aria-pressed", b.dataset.view === state.view);
  cal ? renderCalendar() : renderList();
}

function renderList() {
  const q = $("#q").value.trim().toLowerCase();
  const muni = $("#municipality").value;
  const from = $("#from").value || state.today;
  const to = $("#to").value || "9999-12-31";
  const expand = $("#expand").checked;

  const items = [];
  for (const e of state.events) {
    if (!matches(e, q, muni)) continue;
    const occ = e.occasions.filter((o) => o.date_end >= from && o.date_start <= to);
    if (!occ.length) continue;
    for (const o of expand ? occ : [occ[0]]) items.push({ e, o, occ });
  }
  items.sort((a, b) => {
    const da = a.o.date_start < from ? from : a.o.date_start;
    const db = b.o.date_start < from ? from : b.o.date_start;
    return da.localeCompare(db) || (a.o.time_start || "").localeCompare(b.o.time_start || "") || a.e.title.localeCompare(b.e.title, "sv");
  });

  const nEvents = new Set(items.map((i) => i.e.id)).size;
  $("#count").textContent = expand ? `${items.length} tillfällen (${nEvents} evenemang)` : `${nEvents} evenemang`;

  const frag = document.createDocumentFragment();
  let lastDay = null;
  for (const { e, o, occ } of items) {
    const day = o.date_start < from ? from : o.date_start;
    if (day !== lastDay) {
      const [a, b] = dayLabel(day);
      frag.append(el("h2", { class: "day" }, a, b ? el("small", {}, b) : null));
      lastDay = day;
    }
    frag.append(card(e, o, occ, expand));
  }
  if (!items.length) frag.append(el("p", { class: "muted" }, "Inga evenemang matchar filtret."));
  $("#list").replaceChildren(frag);
}

function card(e, o, occ, expand) {
  const img = e.images[0];
  const cats = e.categories;
  const where = [e.place?.title, e.municipality].filter(Boolean).join(", ");
  const mapUrl = e.place?.lat && e.place?.lon
    ? `https://www.openstreetmap.org/?mlat=${encodeURIComponent(e.place.lat)}&mlon=${encodeURIComponent(e.place.lon)}#map=15/${encodeURIComponent(e.place.lat)}/${encodeURIComponent(e.place.lon)}`
    : null;
  const others = occ.filter((x) => x !== o);

  return el("article", { class: "card" },
    img ? el("img", { class: "img", src: img.medium, alt: img.alt, loading: "lazy", onclick: () => openImage(img) })
        : el("div", { class: "img" }),
    el("div", {},
      el("h3", {}, e.url ? el("a", { href: e.url, target: "_blank", rel: "noopener" }, e.title) : e.title),
      el("div", { class: "meta" },
        el("span", {}, "🕒 ", timeText(o)),
        where ? el("span", {}, "📍 ", mapUrl ? el("a", { href: mapUrl, target: "_blank", rel: "noopener" }, where) : where) : null,
        e.organizer ? el("span", {}, "👤 ", e.organizer) : null,
        el("span", { class: "src" }, "Källa: ", e.sources.map((x) => x.name).join(", "))),
      el("div", { class: "badges" }, cats.map((c) => el("span", { class: "badge", style: `--c:${c.color}`, title: c.description }, `${c.icon} ${c.title}`))),
      el("p", { class: "typedesc" }, cats.map((c) => c.description).join(" ")),
      e.summary ? el("p", { class: "summary" }, e.summary) : null,
      !expand && others.length ? el("div", { class: "dates" }, el("small", { class: "muted" }, "Fler tillfällen:"),
        others.slice(0, 12).map((x) => el("span", {}, fmtShort.format(parseDate(x.date_start)) + (x.time_start ? " " + x.time_start : ""))),
        others.length > 12 ? el("small", { class: "muted" }, `+${others.length - 12} till`) : null) : null,
      e.description || e.images.length > 1 ? el("details", {},
        el("summary", {}, "Beskrivning och bilder"),
        e.description ? el("p", { class: "desc" }, e.description) : null,
        e.place?.address ? el("p", { class: "muted" }, "Adress: " + e.place.address) : null,
        el("div", { class: "thumbs" }, e.images.map((i) => el("img", { src: i.small, alt: i.alt, loading: "lazy", onclick: () => openImage(i) })))) : null,
      el("div", { class: "links" },
        e.url ? el("a", { href: e.url, target: "_blank", rel: "noopener" }, "Mer information ↗") : null,
        e.sources.filter((x) => x.url && x.url !== e.url).map((x) =>
          el("a", { href: x.url, target: "_blank", rel: "noopener" }, `${x.name} ↗`)),
        e.booking_link ? el("a", { href: e.booking_link, target: "_blank", rel: "noopener" }, "Biljetter ↗") : null,
        e.website_link ? el("a", { href: e.website_link, target: "_blank", rel: "noopener" }, "Webbplats ↗") : null)));
}

let t;
$("#q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(render, 150); });
for (const id of ["#municipality", "#source", "#from", "#to", "#expand"]) $(id).addEventListener("change", render);
$("#reset").addEventListener("click", () => {
  $("#q").value = ""; $("#municipality").value = ""; $("#source").value = ""; $("#from").value = ""; $("#to").value = "";
  $("#expand").checked = false; state.cats.clear(); buildFilters(); render();
});
$("#refresh").addEventListener("click", refreshEvents);
for (const b of document.querySelectorAll(".viewtoggle button")) {
  b.addEventListener("click", () => { state.view = b.dataset.view; store("view", state.view); render(); });
}
$("#lightbox").addEventListener("click", (ev) => { if (ev.target.id === "lightbox") ev.target.close(); });
load();
