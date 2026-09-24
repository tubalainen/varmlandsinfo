"use strict";

const $ = (s) => document.querySelector(s);
function stored(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
}
function store(key, value) {
  try { localStorage.setItem(key, value); } catch { /* inte kritiskt */ }
}

const state = { events: [], today: null, cats: new Set(), view: "list", route: null, calMonth: null, meta: {} };

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

const ext = (href, label, cls = "btn btn-sm", ico = "external") =>
  el("a", { class: cls, href, target: "_blank", rel: "noopener" }, icon(ico), label);

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

// ---------------------------------------------------------------- navigering

const ROUTES = {
  lista: { view: "view-events", title: "Evenemang", icon: "list" },
  kalender: { view: "view-events", title: "Kalender", icon: "calendar" },
  fraga: { view: "view-chat" },
  om: { view: "view-about" },
};

function currentRoute() {
  const r = location.hash.replace(/^#\/?/, "");
  return ROUTES[r] ? r : stored("route", "lista");
}

function navigate() {
  const r = currentRoute();
  // Startsidan utan adress får den valda vyns adress, så att bakåtknappen blir rätt
  if (!ROUTES[location.hash.replace(/^#\/?/, "")]) history.replaceState(null, "", `#/${r}`);
  state.route = r;
  if (r === "lista" || r === "kalender") store("route", r);
  for (const id of ["view-events", "view-chat", "view-about"]) $(`#${id}`).hidden = ROUTES[r].view !== id;
  for (const a of document.querySelectorAll(".nav a")) {
    if (a.dataset.route === r) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  document.body.classList.remove("nav-open");
  $("#scrim").hidden = true;
  if (ROUTES[r].view === "view-events") {
    state.view = r === "kalender" ? "calendar" : "list";
    document.title = `${ROUTES[r].title} i Värmland`;
    render();
  } else if (r === "fraga") {
    document.title = "Fråga AI – Värmlandsinfo";
    window.chatView?.show();
  } else {
    document.title = "Om applikationen – Värmlandsinfo";
    window.renderAbout?.();
  }
  window.scrollTo(0, 0);
}

function setNav(open) {
  document.body.classList.toggle("nav-open", open);
  $("#scrim").hidden = !open;
}

// ---------------------------------------------------------------- data

const fmtUpdated = (iso) => {
  const d = new Date(iso);
  return `${d.getDate()}/${d.getMonth() + 1} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

let statusTimer;
/** Meddelande i menyn (t.ex. fel vid hämtning). Försvinner av sig självt om clearAfter anges. */
function flash(text, clearAfter = 0) {
  clearTimeout(statusTimer);
  $("#status").textContent = text;
  if (clearAfter) statusTimer = setTimeout(() => { $("#status").textContent = ""; }, clearAfter);
}

function showStatus(data) {
  // Bara sådant som kräver uppmärksamhet visas, i övrigt är raden tom
  if (data.refreshing && !data.events.length) flash("Hämtar evenemang … (laddar om strax)");
  else if (!data.events.length && data.error) flash(`Kunde inte hämta: ${data.error}`);
  else if (data.storage?.error) flash(data.storage.error);
  else flash("");
  const upd = $("#updated");
  upd.textContent = data.updated ? `uppdaterad ${fmtUpdated(data.updated)}` : "";
  upd.title = data.updated ? `Evenemangen hämtades senast ${fmtTime(data.updated)}` : "";
  $("#nav-count").textContent = data.events.length ? String(data.events.length) : "";
  const v = $("#app-version");
  v.textContent = data.version ? `v${data.version}` : "";
  if (data.release_url) v.href = data.release_url;
}

function renderSources() {
  $("#sources").replaceChildren(...Object.values(state.sources || {}).map((x) => {
    const cls = !x.enabled ? "off" : x.error ? "err" : "";
    const title = x.error || x.config_error || `Senast hämtad ${fmtTime(x.updated)}`;
    return el("li", {}, el("a", { href: x.homepage, target: "_blank", rel: "noopener", title },
      el("span", { class: `src-dot ${cls}` }),
      el("span", { class: "name" }, x.title),
      el("span", { class: `src-count ${cls}` }, !x.enabled ? "av" : x.error ? "fel" : String(x.count))));
  }));
}

async function load() {
  try {
    const r = await fetch("/api/events");
    const data = await r.json();
    state.events = data.events;
    state.today = data.today;
    state.chat = data.chat;
    state.sources = data.sources;
    state.meta = data;
    showStatus(data);
    renderSources();
    if (!data.events.length) setTimeout(load, 5000);
    $("#from").min = $("#to").min = state.today;
    buildFilters();
    if (state.route === "om") window.renderAbout?.();
    else render();
  } catch (e) {
    flash("Fel vid hämtning: " + e);
    setTimeout(load, 10000);
  }
}

// ---------------------------------------------------------------- filter

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

  const counts = new Map();
  for (const e of state.events) for (const c of e.categories) {
    const x = counts.get(c.title) || { ...c, n: 0 };
    x.n++; counts.set(c.title, x);
  }
  // Gratis först, sedan efter antal
  const order = (c) => (c.title === "Gratis" ? -1e9 : -c.n);
  $("#cats").replaceChildren(...[...counts.values()].sort((a, b) => order(a) - order(b)).map((c) =>
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

// ---------------------------------------------------------------- lista

function render() {
  if (!state.today || $("#view-events").hidden) return;
  const cal = state.view === "calendar";
  document.body.classList.toggle("cal-mode", cal);
  $("#list").hidden = cal;
  $("#calendar").hidden = !cal;
  cal ? renderCalendar() : renderList();
}

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const plusDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

/** Datumintervall för datumvalet: [från, till] som ÅÅÅÅ-MM-DD. */
function dateRange() {
  const today = parseDate(state.today);
  const dow = (today.getDay() + 6) % 7;               // 0 = måndag
  const sunday = plusDays(today, 6 - dow);
  switch ($("#when").value) {
    case "today": return [iso(today), iso(today)];
    case "tomorrow": return [iso(plusDays(today, 1)), iso(plusDays(today, 1))];
    case "weekend": return [iso(dow >= 4 ? today : plusDays(sunday, -2)), iso(sunday)];   // fre–sön
    case "week": return [iso(today), iso(sunday)];
    case "nextweek": return [iso(plusDays(sunday, 1)), iso(plusDays(sunday, 7))];
    case "month": return [iso(today), iso(new Date(today.getFullYear(), today.getMonth() + 1, 0))];
    case "nextmonth": return [iso(new Date(today.getFullYear(), today.getMonth() + 1, 1)),
                              iso(new Date(today.getFullYear(), today.getMonth() + 2, 0))];
    case "custom": return [$("#from").value || state.today, $("#to").value || "9999-12-31"];
    default: return [state.today, "9999-12-31"];
  }
}

function renderList() {
  const q = $("#q").value.trim().toLowerCase();
  const muni = $("#municipality").value;
  let [from, to] = dateRange();
  if (from < state.today) from = state.today;
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
  if (!items.length) frag.append(el("p", { class: "empty" }, "Inga evenemang matchar filtret."));
  $("#list").replaceChildren(frag);
}

/** Google Maps-länk: exakt position om koordinater finns, annars sökning på plats, adress och kommun. */
function mapUrl(e) {
  const p = e.place || {};
  const query = p.lat && p.lon ? `${p.lat},${p.lon}`
    // Bara lokalens namn (före kommatecknet), inte scen eller sal: "Scalateatern, Källaren" -> "Scalateatern"
    : p.title ? [p.title.split(",")[0], p.address, e.municipality].filter(Boolean).join(", ") : null;
  return query ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}` : null;
}

function card(e, o, occ, expand) {
  const img = e.images[0];
  const cats = e.categories;
  const where = [e.place?.title, e.municipality].filter(Boolean).join(", ");
  const map = mapUrl(e);
  const others = occ.filter((x) => x !== o);

  return el("article", { class: "card" },
    img ? el("img", { class: "img", src: img.medium, alt: img.alt, loading: "lazy", onclick: () => openImage(img) })
        : el("div", { class: "img" }),
    el("div", {},
      el("h3", {}, e.url ? el("a", { href: e.url, target: "_blank", rel: "noopener" }, e.title) : e.title),
      el("div", { class: "meta" },
        el("span", {}, icon("clock"), timeText(o)),
        where ? el("span", {}, icon("pin"), map ? el("a", { href: map, target: "_blank", rel: "noopener", title: "Visa på Google Maps" }, where) : where) : null,
        e.organizer ? el("span", {}, icon("user"), e.organizer) : null,
        el("span", { class: "src" }, icon("layers"), e.sources.map((x) => x.name).join(", "))),
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
        e.url ? ext(e.url, "Mer information", "btn btn-sm btn-primary") : null,
        e.booking_link ? ext(e.booking_link, "Biljetter", "btn btn-sm", "ticket") : null,
        e.sources.filter((x) => x.url && x.url !== e.url).map((x) => ext(x.url, x.name)),
        e.website_link ? ext(e.website_link, "Webbplats") : null)));
}

// ---------------------------------------------------------------- start

let t;
$("#q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(render, 150); });
for (const id of ["#municipality", "#source", "#from", "#to", "#expand"]) $(id).addEventListener("change", render);
$("#when").addEventListener("change", () => {
  $("#custom-dates").hidden = $("#when").value !== "custom";
  render();
});
$("#reset").addEventListener("click", () => {
  for (const id of ["#q", "#municipality", "#source", "#when", "#from", "#to"]) $(id).value = "";
  $("#custom-dates").hidden = true;
  $("#expand").checked = false; state.cats.clear(); buildFilters(); render();
});
$("#nav-open").addEventListener("click", () => setNav(true));
$("#nav-close").addEventListener("click", () => setNav(false));
$("#scrim").addEventListener("click", () => setNav(false));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") setNav(false); });
$("#lightbox").addEventListener("click", (ev) => { if (ev.target.id === "lightbox") ev.target.close(); });
window.addEventListener("hashchange", navigate);
document.addEventListener("DOMContentLoaded", () => { navigate(); load(); });
