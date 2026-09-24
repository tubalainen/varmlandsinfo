"use strict";

(() => {
  const $ = (s) => document.querySelector(s);
  const panel = $("#chat"), log = $("#chat-log"), form = $("#chat-form"), input = $("#chat-input");
  const history = [];
  let busy = false;

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
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.textContent = text;
    log.append(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  async function ask(question) {
    if (busy || !question.trim()) return;
    busy = true;
    form.querySelector("button").disabled = true;
    history.push({ role: "user", content: question });
    addMsg("user", question);
    const msg = addMsg("assistant");
    const body = document.createElement("div");
    body.className = "typing";
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
          else if (ev.type === "delta") { answer += ev.text; renderMarkdown(body, answer); log.scrollTop = log.scrollHeight; }
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
        const d = document.createElement("details");
        d.className = "sources";
        const s = document.createElement("summary");
        s.textContent = `Underlag: ${sources.length} evenemang`;
        const ul = document.createElement("ul");
        for (const src of sources) {
          const li = document.createElement("li");
          li.append(`${src.date} – `, src.url ? link(src.title, src.url) : src.title);
          ul.append(li);
        }
        d.append(s, ul);
        msg.append(d);
      }
      busy = false;
      form.querySelector("button").disabled = false;
      log.scrollTop = log.scrollHeight;
      input.focus();
    }
  }

  async function open() {
    panel.hidden = false;
    input.focus();
    try {
      const st = await (await fetch("/api/chat/status")).json();
      $("#chat-model").textContent = st.model || "";
      if (st.error && !panel.dataset.warned) {
        panel.dataset.warned = "1";
        addMsg("assistant error", "⚠️ " + st.error);
      }
    } catch { /* statusen är bara information */ }
  }

  $("#chat-open").addEventListener("click", open);
  $("#chat-close").addEventListener("click", () => { panel.hidden = true; });
  $("#chat-clear").addEventListener("click", () => {
    history.length = 0;
    log.querySelectorAll(".msg:not(.intro)").forEach((n) => n.remove());
    delete panel.dataset.warned;
  });
  form.addEventListener("submit", (e) => { e.preventDefault(); const q = input.value; input.value = ""; ask(q); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  log.addEventListener("click", (e) => {
    if (e.target.classList.contains("ex")) { e.preventDefault(); ask(e.target.textContent); }
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) panel.hidden = true; });
})();
