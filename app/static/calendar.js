"use strict";

// Kalendervy: en månad i taget, en vecka (mån–sön) per rad.
// Använder hjälpfunktionerna från app.js (el, state, matches, card, timeText, parseDate).

const CAL_MAX_PER_DAY = 4;
const fmtMonth = new Intl.DateTimeFormat("sv-SE", { month: "long", year: "numeric" });
const fmtDialogDay = new Intl.DateTimeFormat("sv-SE", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const WEEKDAY_SHORT = ["Mån", "Tis", "Ons", "Tor", "Fre", "Lör", "Sön"];

const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const mondayOf = (d) => addDays(d, -((d.getDay() + 6) % 7));

function isoWeek(d) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return Math.ceil(((t - yearStart) / 86400000 + 1) / 7);
}

/** Filtrerade evenemang per dag inom [start, end]: Map<"ÅÅÅÅ-MM-DD", [{e, o}]> */
function eventsByDay(start, end) {
  const q = $("#q").value.trim().toLowerCase();
  const muni = $("#municipality").value;
  const lo = isoDay(start), hi = isoDay(end);
  const map = new Map();
  for (const e of state.events) {
    if (!matches(e, q, muni)) continue;
    for (const o of e.occasions) {
      if (o.date_end < lo || o.date_start > hi) continue;
      // Tillfällen som sträcker sig över flera dagar visas på varje dag
      for (let d = parseDate(o.date_start < lo ? lo : o.date_start); isoDay(d) <= (o.date_end > hi ? hi : o.date_end); d = addDays(d, 1)) {
        const key = isoDay(d);
        if (!map.has(key)) map.set(key, []);
        map.get(key).push({ e, o });
      }
    }
  }
  for (const list of map.values()) {
    list.sort((a, b) => (a.o.time_start || "99").localeCompare(b.o.time_start || "99") || a.e.title.localeCompare(b.e.title, "sv"));
  }
  return map;
}

function lastEventMonth() {
  let last = state.today;
  for (const e of state.events) for (const o of e.occasions) if (o.date_start > last) last = o.date_start;
  const d = parseDate(last);
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function renderCalendar() {
  if (!state.today) return;
  const today = parseDate(state.today);
  const firstMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  const lastMonth = lastEventMonth();
  if (!state.calMonth) state.calMonth = firstMonth;
  if (state.calMonth < firstMonth) state.calMonth = firstMonth;
  if (state.calMonth > lastMonth) state.calMonth = lastMonth;

  const month = state.calMonth;
  const monthEnd = new Date(month.getFullYear(), month.getMonth() + 1, 0);
  // Passerade veckor saknar evenemang, så innevarande månad börjar på veckan med idag
  const gridStart = new Date(Math.max(mondayOf(month), mondayOf(today)));
  const gridEnd = addDays(mondayOf(monthEnd), 6);
  const byDay = eventsByDay(gridStart, gridEnd);

  const go = (delta) => { state.calMonth = new Date(month.getFullYear(), month.getMonth() + delta, 1); renderCalendar(); };
  const title = fmtMonth.format(month);
  const head = el("div", { class: "cal-head" },
    el("button", { type: "button", onclick: () => go(-1), disabled: month <= firstMonth ? "" : null, "aria-label": "Föregående månad" }, icon("left")),
    el("h2", {}, title.charAt(0).toUpperCase() + title.slice(1)),
    el("button", { type: "button", onclick: () => go(1), disabled: month >= lastMonth ? "" : null, "aria-label": "Nästa månad" }, icon("right")),
    el("button", { type: "button", class: "cal-today", onclick: () => { state.calMonth = firstMonth; renderCalendar(); } }, "Idag"));

  const grid = el("div", { class: "cal-grid", role: "grid" },
    el("div", { class: "cal-wk cal-dow" }, "v."),
    WEEKDAY_SHORT.map((d) => el("div", { class: "cal-dow" }, d)));

  let monthCount = 0;
  const monthEvents = new Set();
  for (let week = gridStart; week <= gridEnd; week = addDays(week, 7)) {
    grid.append(el("div", { class: "cal-wk" }, String(isoWeek(week))));
    for (let i = 0; i < 7; i++) {
      const d = addDays(week, i);
      const key = isoDay(d);
      const items = byDay.get(key) || [];
      const inMonth = d.getMonth() === month.getMonth();
      if (inMonth) { monthCount += items.length; items.forEach((x) => monthEvents.add(x.e.id)); }
      const cls = ["cal-day", inMonth ? "" : "other", key === state.today ? "today" : "", key < state.today ? "past" : "", i >= 5 ? "weekend" : ""].filter(Boolean).join(" ");

      const cell = el("div", { class: cls, role: "gridcell",
          onclick: (ev) => { if (!ev.target.closest("a, button")) openDay(key, items); } },
        el("button", { type: "button", class: "cal-num", onclick: () => openDay(key, items), disabled: items.length ? null : "",
          "aria-label": `${fmtDialogDay.format(d)}, ${items.length} evenemang` },
          el("span", {}, String(d.getDate())),
          items.length ? el("span", { class: "cal-count" }, String(items.length)) : null),
        el("div", { class: "cal-evs" },
          items.slice(0, CAL_MAX_PER_DAY).map(({ e, o }) => {
            const c = e.categories[0];
            return el("a", { class: "cal-ev", href: e.url || "#", target: "_blank", rel: "noopener", style: `--c:${c.color}`,
              title: `${e.title}\n${timeText(o)}${e.municipality ? " · " + e.municipality : ""}\n${c.title}` },
              el("span", { class: "cal-ico" }, c.icon),
              o.time_start ? el("span", { class: "cal-time" }, o.time_start) : null,
              el("span", { class: "cal-title" }, e.title));
          }),
          items.length > CAL_MAX_PER_DAY
            ? el("button", { type: "button", class: "cal-more", onclick: () => openDay(key, items) }, `+${items.length - CAL_MAX_PER_DAY} till`)
            : null));
      grid.append(cell);
    }
  }

  $("#count").textContent = `${monthEvents.size} evenemang (${monthCount} tillfällen) i ${title}`;
  $("#calendar").replaceChildren(head, grid);
}

function openDay(key, items) {
  if (!items.length) return;
  const dlg = $("#daydialog");
  const text = fmtDialogDay.format(parseDate(key));
  dlg.querySelector("h2").textContent = `${text.charAt(0).toUpperCase() + text.slice(1)} · ${items.length} evenemang`;
  dlg.querySelector(".daylist").replaceChildren(...items.map(({ e, o }) => card(e, o, [o], true)));
  dlg.showModal();
  dlg.querySelector(".daylist").scrollTop = 0;
}

$("#daydialog").addEventListener("click", (ev) => { if (ev.target.id === "daydialog") ev.target.close(); });
