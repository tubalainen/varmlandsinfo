"use strict";

// Fråga AI: egen sida med förslagskort, snabbval och strömmade svar från Ollama.
(() => {
  const log = $("#chat-log"), form = $("#chat-form"), input = $("#chat-input"), welcome = $("#chat-welcome");
  const sendBtn = form.querySelector(".send");
  const history = [];
  let busy = false, statusLoaded = false;

  const SUGGESTIONS = [
    { title: "I helgen", tag: "Helg", q: "Vad händer i Värmland i helgen? Ge mig de bästa tipsen." },
    { title: "Barn & familj", tag: "Barn", q: "Finns det några barnaktiviteter i Karlstad nästa vecka?" },
    { title: "Konserter", tag: "Musik", q: "Vilka konserter finns i Värmland den här månaden?" },
    { title: "Färjestad BK", tag: "Sport", q: "När spelar Färjestad hemma nästa gång?" },
    { title: "Teater & humor", tag: "Scen", q: "Vilka föreställningar går på Scalateatern och Karlstad CCC framöver?" },
    { title: "Idag", tag: "Idag", q: "Vad kan jag göra idag i Värmland?" },
  ];
  const QUICK = [
    ["Idag", "Vad händer idag?"], ["I helgen", "Vad händer i helgen?"], ["Nästa vecka", "Vad händer nästa vecka?"],
    ["Barn", "Vilka barnaktiviteter finns i helgen?"], ["Musik", "Vilka konserter finns nästa vecka?"],
    ["Sport", "Vilka sportevenemang finns i helgen?"], ["Karlstad", "Vad händer i Karlstad i helgen?"],
    ["Arvika", "Vad händer i Arvika den här månaden?"],
  ];

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

  async function ask(question) {
    question = question.trim();
    if (busy || !question) return;
    busy = true;
    sendBtn.disabled = true;
    history.push({ role: "user", content: question });
    addMsg("user", question);
    const msg = addMsg("assistant");
    const body = el("div", {},
      el("div", { class: "thinking" }, el("span", { class: "dots" }, el("span"), el("span"), el("span")),
        "Den lokala AI-modellen arbetar. Det kan ta en stund …"));
    msg.append(body);
    let answer = "", sources = [];

    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
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
          if (ev.type === "sources") sources = ev.events;
          else if (ev.type === "delta") {
            answer += ev.text;
            body.classList.add("typing");   // skrivmarkör medan svaret strömmar in
            renderMarkdown(body, answer);
            log.scrollTop = log.scrollHeight;
          }
          else if (ev.type === "error") throw new Error(ev.error);
        }
      }
      history.push({ role: "assistant", content: answer });
    } catch (e) {
      msg.classList.add("error");
      answer += (answer ? "\n\n" : "") + "⚠️ " + e.message;
      renderMarkdown(body, answer);
      history.pop(); // frågan besvarades inte, skicka den inte som historik
    } finally {
      body.classList.remove("typing");
      if (sources.length && !msg.classList.contains("error")) {
        msg.append(el("details", { class: "sources" },
          el("summary", {}, `Underlag: ${sources.length} evenemang`),
          el("ul", {}, sources.map((src) => el("li", {}, `${src.date} – `, src.url ? link(src.title, src.url) : src.title)))));
      }
      busy = false;
      sendBtn.disabled = false;
      log.scrollTop = log.scrollHeight;
      input.focus();
    }
  }

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
        model.textContent = `Modell: ${st.model}`;
      } else {
        dot.className = "dot err";
        model.textContent = st.enabled ? `Modell: ${st.model} · ${st.error}` : "Inte konfigurerad: sätt OLLAMA_URL i .env";
      }
    } catch {
      dot.className = "dot err";
      model.textContent = "Kunde inte kontrollera AI-modellen";
    }
  }

  // ---- uppbyggnad
  $("#suggestions").replaceChildren(...SUGGESTIONS.map((s) =>
    el("button", { type: "button", class: "suggestion", onclick: () => ask(s.q) },
      el("span", { class: "top" }, el("strong", {}, s.title), el("span", { class: "tag" }, s.tag)),
      el("span", { class: "text" }, s.q))));
  $("#quick").replaceChildren(el("span", { class: "label" }, "Snabbval:"), ...QUICK.map(([label, q]) =>
    el("button", { type: "button", onclick: () => ask(q) }, icon("tag"), label)));

  form.addEventListener("submit", (e) => { e.preventDefault(); const q = input.value; input.value = ""; autosize(); ask(q); });
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  $("#chat-clear").addEventListener("click", () => {
    history.length = 0;
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
