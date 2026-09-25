"use strict";

// Fråga AI: egen sida med förslagskort, snabbval och strömmade svar från Ollama.
(() => {
  const log = $("#chat-log"), form = $("#chat-form"), input = $("#chat-input"), welcome = $("#chat-welcome");
  const sendBtn = form.querySelector(".send");
  let busy = false, statusLoaded = false;

  // ---- enkel och säker markdown-rendering (bygger DOM-noder, aldrig innerHTML)
  const safeUrl = (u) => /^https?:\/\//i.test(u) ? u : null;

  function inline(text) {
    const out = [];
    const re = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*([^*]+)\*\*|(https?:\/\/[^\s)<>\]]+)/g;
    let last = 0, m;
    while ((m = re.exec(text))) {
      if (m.index > last) out.push(document.createTextNode(text.slice(last, m.index)));
      if (m[1]) out.push(link(m[1], m[2]));
      else if (m[3]) { const b = document.createElement("strong"); b.append(...inline(m[3])); out.push(b); }
      else out.push(link(m[4], m[4]));
      last = re.lastIndex;
    }
    if (last < text.length) out.push(document.createTextNode(text.slice(last)));
    return out;
  }

  function link(label, url) {
    if (!safeUrl(url)) return document.createTextNode(label);
    const a = document.createElement("a");
    a.href = url; a.target = "_blank"; a.rel = "noopener"; a.textContent = label;
    return a;
  }

  function renderMarkdown(target, text) {
    const frag = document.createDocumentFragment();
    let list = null;
    for (const raw of text.split("\n")) {
      const line = raw.trimEnd();
      const item = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
      if (item) {
        if (!list) { list = document.createElement("ul"); frag.append(list); }
        const li = document.createElement("li"); li.append(...inline(item[1])); list.append(li);
        continue;
      }
      list = null;
      if (!line.trim()) continue;
      const h = line.match(/^#{1,6}\s+(.*)$/);
      const p = document.createElement("p");
      if (h) { const b = document.createElement("strong"); b.append(...inline(h[1])); p.append(b); }
      else p.append(...inline(line));
      frag.append(p);
    }
    target.replaceChildren(frag);
  }

  // ---- samtalet (sessionen) finns på servern, fliken sparar bara sitt sessions-id
  const SESSION_KEY = "chat-session";
  let sessionId = null;
  try { sessionId = sessionStorage.getItem(SESSION_KEY); } catch { /* utan lagring blir varje sidladdning ett nytt samtal */ }
  function setSession(id) {
    sessionId = id;
    try { id ? sessionStorage.setItem(SESSION_KEY, id) : sessionStorage.removeItem(SESSION_KEY); } catch { /* se ovan */ }
  }
  const sessionHeaders = () => (sessionId ? { "X-Chat-Session": sessionId } : {});

  // ---- chattlogik
  function addMsg(role, text = "") {
    welcome.hidden = true;
    $("#chat-clear").hidden = false;
    const div = el("div", { class: `msg ${role}` });
    div.textContent = text;
    log.append(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  // Noteringar under ett svar: sökresultat, sparat svar och underlaget
  function decorate(msg, meta, sources, web = []) {
    if (meta.mode === "search") {
      msg.append(el("p", { class: "cached-note" }, icon("search"),
        "Sökresultat direkt från appen. Frågan gällde att hitta evenemang, så ingen AI behövdes."));
    } else if (meta.cached) {
      const when = meta.saved ? new Date(meta.saved).toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" }) : "";
      msg.append(el("p", { class: "cached-note" }, icon("database"),
        `Sparat svar${when ? " från " + when : ""}. Evenemangen har inte ändrats sedan dess, så AI:n behövde inte svara igen.`));
    }
    if (sources.length && meta.mode !== "search" && !msg.classList.contains("error")) {
      msg.append(el("details", { class: "sources" },
        el("summary", {}, `Underlag: ${sources.length} evenemang`),
        el("ul", {}, sources.map((src) => el("li", {}, `${src.date} – `, src.url ? link(src.title, src.url) : src.title)))));
    }
    if (web.length && !msg.classList.contains("error")) {
      msg.append(el("details", { class: "sources" },
        el("summary", {}, `Från webben: ${web.length} ${web.length === 1 ? "träff" : "träffar"}`),
        el("ul", {}, web.map((w) => el("li", {}, link(w.title, w.url))))));
    }
  }

  function note(msg, iconName, text) {
    msg.append(el("p", { class: "cached-note" }, icon(iconName), text));
  }

  async function ask(question) {
    question = question.trim();
    if (busy || !question) return;
    busy = true;
    sendBtn.disabled = true;
    const hadConversation = !!log.querySelector(".msg");
    addMsg("user", question);
    const msg = addMsg("assistant");
    const status = el("span", {}, "Söker bland evenemangen. Kräver frågan AI kan det ta en stund …");
    const body = el("div", {},
      el("div", { class: "thinking" }, el("span", { class: "dots" }, el("span"), el("span"), el("span")), status));
    msg.append(body);
    let answer = "", sources = [], web = [], meta = {}, expired = false;

    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...sessionHeaders() },
        body: JSON.stringify({ question }),
      });
      if (!r.ok) {
        let error = `HTTP ${r.status}`;
        try { error = (await r.json()).error || error; } catch { /* inget JSON-svar */ }
        throw new Error(error);
      }
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
          if (!line.trim()) continue;
          const ev = JSON.parse(line);
          if (ev.type === "session") { expired = ev.expired && hadConversation; setSession(ev.id); }
          else if (ev.type === "queue") {
            status.textContent = ev.position
              ? `Den lokala AI-modellen svarar på andra frågor just nu. Du är nummer ${ev.position} i kön …`
              : "Din tur! Den lokala AI-modellen arbetar. Det kan ta en stund …";
          }
          else if (ev.type === "sources") sources = ev.events;
          else if (ev.type === "websearch") {
            status.textContent = ev.found === undefined ? "Söker på webben efter mer information …"
              : `${ev.found ? `Hittade ${ev.found} webbträffar. ` : ""}Den lokala AI-modellen arbetar. Det kan ta en stund …`;
          }
          else if (ev.type === "web") web = ev.results;
          else if (ev.type === "done") meta = ev;
          else if (ev.type === "delta") {
            answer += ev.text;
            body.classList.add("typing");   // skrivmarkör medan svaret strömmar in
            renderMarkdown(body, answer);
            log.scrollTop = log.scrollHeight;
          }
          else if (ev.type === "error") throw new Error(ev.error);
        }
      }
    } catch (e) {
      msg.classList.add("error");
      answer += (answer ? "\n\n" : "") + "⚠️ " + e.message;
      renderMarkdown(body, answer);
    } finally {
      body.classList.remove("typing");
      if (expired) note(msg, "info", "Det tidigare samtalet hade gått ut, så frågan besvarades som ett nytt samtal.");
      decorate(msg, meta, sources, web);
      busy = false;
      sendBtn.disabled = false;
      log.scrollTop = log.scrollHeight;
      input.focus();
    }
  }

  // Visar samtalet igen efter omladdning av sidan
  async function restore() {
    if (!sessionId) return;
    try {
      const s = await (await fetch("/api/chat/session", { headers: sessionHeaders() })).json();
      if (log.querySelector(".msg")) return;   // en ny fråga hann ställas medan samtalet hämtades
      for (const m of s.messages) {
        if (m.role === "user") { addMsg("user", m.content); continue; }
        const msg = addMsg("assistant"), body = el("div");
        renderMarkdown(body, m.content);
        msg.append(body);
        decorate(msg, m, m.sources || [], m.web || []);
      }
    } catch { /* samtalet kunde inte hämtas, börja om */ }
  }
  restore();

  function autosize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  }

  async function loadStatus() {
    const dot = $("#chat-dot"), model = $("#chat-model");
    try {
      const st = await (await fetch("/api/chat/status")).json();
      statusLoaded = true;
      if (st.enabled && st.reachable && !st.error) {
        dot.className = "dot ok";
        model.textContent = `Modell: ${st.model}` + (st.websearch ? " · Webbsökning på" : "");
      } else {
        dot.className = "dot err";
        model.textContent = st.enabled ? `Modell: ${st.model} · ${st.error}` : "Inte konfigurerad: sätt OLLAMA_URL i .env";
      }
    } catch {
      dot.className = "dot err";
      model.textContent = "Kunde inte kontrollera AI-modellen";
    }
  }

  // ---- uppbyggnad: fördefinierade frågor hämtas från servern (deras svar sparas alltid)
  async function loadPresets() {
    try {
      const p = await (await fetch("/api/chat/presets")).json();
      $("#suggestions").replaceChildren(...p.suggestions.map((s) =>
        el("button", { type: "button", class: "suggestion", onclick: () => ask(s.q) },
          el("span", { class: "top" }, el("strong", {}, s.title), el("span", { class: "tag" }, s.tag)),
          el("span", { class: "text" }, s.q))));
      $("#quick").replaceChildren(el("span", { class: "label" }, "Snabbval:"), ...p.quick.map((x) =>
        el("button", { type: "button", onclick: () => ask(x.q) }, icon("tag"), x.label)));
    } catch { /* förslagen är inte nödvändiga för att chatta */ }
  }
  loadPresets();

  form.addEventListener("submit", (e) => { e.preventDefault(); const q = input.value; input.value = ""; autosize(); ask(q); });
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  $("#chat-clear").addEventListener("click", () => {
    if (busy) return;
    if (sessionId) fetch("/api/chat/session", { method: "DELETE", headers: sessionHeaders() }).catch(() => {});
    setSession(null);
    log.querySelectorAll(".msg").forEach((n) => n.remove());
    welcome.hidden = false;
    $("#chat-clear").hidden = true;
    input.focus();
  });

  window.chatView = {
    show() {
      if (!statusLoaded) loadStatus();
      setTimeout(() => input.focus(), 50);
    },
  };
})();
