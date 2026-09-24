"use strict";

// Sidan "Om applikationen": beskriver funktionerna och visar aktuell status för källor och version.
(() => {
  const REPO = "https://github.com/tubalainen/varmlandsinfo";

  const FEATURES = [
    ["panel", "Anpassningsbar meny", "På datorn kan menyn fällas ihop till en smal list med ikoner för mer plats. Valet sparas till nästa besök."],
    ["list", "Evenemangslista", "Alla kommande och pågående evenemang, dag för dag. Varje evenemang visar tid, plats med länk till Google Maps, arrangör, typ, beskrivning, bilder och länkar till mer information och biljetter."],
    ["calendar", "Kalender", "En månad i taget med en vecka per rad och veckonummer. Evenemangen är färgkodade per typ. Klicka på en dag för att se alla dagens evenemang."],
    ["filter", "Filter och sök", "Sök i fritext och filtrera på evenemangstyp, kommun, källa och datum (idag, i helgen, nästa vecka …). Kategorin Gratis visar evenemang med fri entré. Återkommande evenemang kan visas en gång eller för varje tillfälle."],
    ["sparkles", "Fråga AI", "Ställ frågor på vanlig svenska, till exempel \"Vad händer i Karlstad i helgen?\". AI:n väljer ut relevanta evenemang, svarar med länkar och visar vilket underlag svaret bygger på. Följdfrågor fungerar."],
    ["layers", "Flera källor", "Evenemang hämtas från flera källor och slås ihop. Samma evenemang från flera källor visas en gång, med länkar till alla källor."],
    ["refresh", "Alltid aktuellt", "Evenemangen hämtas automatiskt en gång per dygn. Källorna anropas sparsamt, och senast uppdaterad visas vid versionen i menyn."],
    ["database", "Sparad data", "Allt som hämtas sparas på servern. Vid omstart visas evenemangen direkt, utan nya anrop till källorna."],
    ["shield", "Lokalt och privat", "Appen körs hemma i Docker. AI-chatten använder en egen Ollama-server, så frågorna lämnar aldrig ditt nätverk."],
  ];

  const SOURCE_INFO = {
    visitvarmland: "Evenemang i hela Värmland via Visit Värmlands öppna API. Omfattar även Karlstads och Hammarö kommuns evenemangskalendrar.",
    ticketmaster: "Konserter, shower och sport på arenor i Värmland via Ticketmasters API (kräver API-nyckel).",
    ccc: "Konserter och shower i Karlstad CCC:s konserthall Solasalen.",
    scala: "Teater, musik och humor på Scalateaterns scener i Karlstad.",
    shl: "Färjestad BK:s hemmamatcher i Löfbergs Arena, med tider från SHL:s spelschema.",
  };

  const section = (ico, title, ...content) => el("section", {}, el("h2", {}, icon(ico), title), ...content);

  function status(s) {
    if (!s.enabled) return el("span", { class: "status-off" }, "Avstängd");
    if (s.error) return el("span", { class: "status-err" }, "Fel");
    return el("span", { class: "status-ok" }, "OK");
  }

  window.renderAbout = () => {
    const m = state.meta || {};
    const sources = Object.entries(m.sources || {});
    const chat = m.chat || {};
    $("#about").replaceChildren(
      section("info", "Vad är Värmlandsinfo?",
        el("p", {}, "Värmlandsinfo samlar evenemang i Värmland från flera källor och visar dem på ett ställe: som lista, i en kalender och via en AI-assistent som svarar på frågor om vad som händer."),
        el("p", { class: "muted" }, `Just nu finns ${m.events?.length ?? "–"} aktuella evenemang, senast uppdaterade ${fmtTime(m.updated)}. Nästa automatiska uppdatering sker ${fmtTime(m.next_refresh)}.`)),

      section("sparkles", "Funktioner",
        el("div", { class: "features" }, FEATURES.map(([ico, title, text]) =>
          el("div", { class: "feature" }, icon(ico), el("h3", {}, title), el("p", {}, text))))),

      section("layers", "Källor",
        el("div", { style: "overflow-x:auto" }, el("table", { class: "src-table" },
          el("thead", {}, el("tr", {}, el("th", {}, "Källa"), el("th", {}, "Innehåll"), el("th", {}, "Evenemang"),
            el("th", {}, "Senast hämtad"), el("th", {}, "Status"))),
          el("tbody", {}, sources.map(([key, s]) => el("tr", {},
            el("td", {}, el("a", { href: s.homepage, target: "_blank", rel: "noopener" }, s.title)),
            el("td", {}, SOURCE_INFO[key] || ""),
            el("td", {}, s.enabled ? String(s.count) : "–"),
            el("td", {}, fmtTime(s.updated)),
            el("td", { title: s.error || s.config_error || "" }, status(s), s.error || s.config_error
              ? el("div", { class: "muted", style: "font-size:.8rem" }, s.error || s.config_error) : null))))))),

      section("message", "AI-chatten",
        el("p", {}, "AI-chatten använder en språkmodell i din egen Ollama-server. För varje fråga tolkar appen tidsuttryck (idag, i helgen, nästa vecka, 3 oktober …), kommuner, evenemangstyper och sökord. Sedan skickar den de mest relevanta evenemangen till modellen, som instrueras att bara svara utifrån dem."),
        el("p", {}, "Modellen körs lokalt i ditt eget nätverk, så frågorna skickas aldrig till någon molntjänst. Det gör att svaren kan ta lite längre tid än hos molntjänster som ChatGPT och Gemini."),
        el("p", {}, "AI:n svarar bara på frågor om evenemang och aktiviteter i appen och ger personliga rekommendationer, till exempel utifrån barns ålder. Andra frågor får ett fast svar, och försök att ändra AI:ns uppdrag stoppas."),
        el("p", {}, "Svaren sparas. Ställs samma fråga samma dag och evenemangen inte har ändrats, visas det sparade svaret direkt utan en ny förfrågan till AI:n. Alla fördefinierade frågor sparas, liksom de 10 senaste egna frågorna."),
        el("p", { class: "muted" }, chat.enabled ? `Modell: ${chat.model}.` : "AI-chatten är inte konfigurerad. Sätt OLLAMA_URL i .env för att aktivera den.")),

      section("code", "Version och källkod",
        el("p", {}, `Du kör version ${m.version ? "v" + m.version : "–"}. Appen är öppen källkod. Ändringar, versioner och instruktioner finns på GitHub.`),
        el("div", { class: "actions" },
          m.release_url ? ext(m.release_url, `Release v${m.version}`, "btn btn-primary") : null,
          ext(`${REPO}/blob/main/CHANGELOG.md`, "Ändringslogg"),
          ext(REPO, "Källkod på GitHub", "btn", "code"))),
    );
  };
})();
