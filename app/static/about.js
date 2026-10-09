"use strict";

// Sidan "Om applikationen": beskriver funktionerna och visar aktuell status för källor och version.
(() => {
  const REPO = "https://github.com/tubalainen/varmlandsinfo";

  const FEATURES = [
    ["panel", "Anpassningsbar meny", "På datorn kan menyn fällas ihop till en smal list med ikoner för mer plats. Valet sparas till nästa besök."],
    ["list", "Evenemangslista", "Alla kommande och pågående evenemang, dag för dag. Under varje dag står evenemang som bara äger rum en dag först, och sedan de som har flera datum, som utställningar och återkommande evenemang. Varje evenemang visar tid, plats med länk till Google Maps, arrangör, typ, beskrivning, bilder och länkar till mer information och biljetter. Saknas bilden, eller går den inte att hämta, visas en tecknad bild för evenemangets typ: ett värmländskt landskap med typens symbol."],
    ["calendar", "Kalender", "En månad i taget med en vecka per rad och veckonummer. Evenemangen är färgkodade per typ. Endagsevenemang står först i varje dag. Klicka på en dag för att se alla dagens evenemang."],
    ["filter", "Filter och sök", "Sök i fritext och filtrera på evenemangstyp, kommun, källa och datum (idag, i helgen, nästa vecka …). Du kan välja flera kommuner och källor samtidigt. Kategorierna står i bokstavsordning. Gratis visar evenemang med fri entré, Loppis visar loppisar, loppmarknader och second hand, Motorsport visar folkrace, rally, rallycross, crosskart, karting, motocross, enduro, speedway med mera, Motorträffar visar bil- och MC-träffar och veteranfordon, SHL visar Färjestads hemmamatcher i SHL, Bandy visar bandymatcher och Handboll visar handbollsmatcher. Film, Spel och quiz, Träffar och caféer samt Böcker och litteratur hittas med ord i titeln, även när källan bara har en allmän kategori. Övrigt är evenemang som inte passar in någon annanstans. Återkommande evenemang visas en gång, på första datumet, med övriga datum i kortet. Med Ett kort per datum visas de på varje datum."],
    ["sparkles", "Fråga AI", "Ställ frågor på vanlig svenska. Enkla sökningar, som \"När spelar Färjestad nästa gång?\", besvaras direkt med en lista. Frågor som kräver en bedömning, som \"Vad skulle passa min 8-åriga son i helgen?\", besvaras av AI:n med länkar och underlag. Följdfrågor fungerar."],
    ["layers", "Flera källor", "Evenemang hämtas från flera källor och slås ihop. Samma evenemang från flera källor visas en gång, med länkar till alla källor."],
    ["refresh", "Alltid aktuellt", "Evenemangen hämtas automatiskt varje förmiddag, från varje källa vid en egen slumpad tid som byts varje dag. Efter varje hämtning städas inaktuell data bort: källor som inte kunde hämtas visar inga gamla evenemang, och gamla AI-svar, bilder, chattsamtal och IP-adresser tas bort. Källorna anropas sparsamt, och när alla källor senast var hämtade visas vid versionen i menyn."],
    ["database", "Sparad data", "Allt som hämtas sparas på servern, även bilderna. Vid omstart visas evenemangen direkt, utan nya anrop till källorna."],
    ["shield", "Lokalt och privat", "Appen körs hemma i Docker. AI-chatten använder en egen Ollama-server, så frågorna lämnar aldrig ditt nätverk."],
  ];
  // Utan Fråga AI (CHAT_ENABLED=false) beskrivs inte AI-chatten
  const NO_CHAT_FEATURES = { sparkles: null, shield: "Appen körs hemma i Docker och laddar inga externa skript, typsnitt eller spårning." };

  const SOURCE_INFO = {
    visitvarmland: "Evenemang i hela Värmland via Visit Värmlands öppna API. Omfattar även Karlstads och Hammarö kommuns evenemangskalendrar.",
    ticketmaster: "Konserter, shower och sport på arenor i Värmland via Ticketmasters API (kräver API-nyckel).",
    ccc: "Konserter och shower i Karlstad CCC:s konserthall Solasalen.",
    scala: "Teater, musik och humor på Scalateaterns scener i Karlstad.",
    greatevent: "Konserter och evenemang från Great Event of Karlstad, bland annat på Löfbergs Arena, Nöjesfabriken och Julins Backyard BBQ.",
    Loppisar: "Loppisar i Värmland: bakluckeloppisen på I2 Norra Fältet i Karlstad med nästa datum från arrangören "
      + "Karlstad Loppis, och loppisar med öppettider per dag från loppisar.com. Kontakta gärna loppisen innan du åker långt.",
    Motorsport: "Motorsporttävlingar och prova på-dagar i Värmland och Karlskoga: bilsport (folkrace, rally, rallycross, crosskart, karting …) "
      + "från Svensk Bilsports tävlingskalender och MC-sport (motocross, enduro, speedway …) från Svemo.",
    shl: "Färjestad BK:s hemmamatcher i Löfbergs Arena, med tider från SHL:s spelschema.",
    handboll: "Handbollsmatcher i Värmland från Svenska Handbollförbundets spelprogram i Profixio: seniorer, herr och dam, i de nationella serierna, Svenska cupen och Handbollförbundet Västs division 2–4, till exempel IF Hellton Karlstads och IFK Hammarös hemmamatcher.",
    Kommunerna: "Evenemang från kommunernas egna evenemangskalendrar, som inte finns hos Visit Värmland: Säffle (bland annat Medis, "
      + "Sagabiografen och biblioteket) och Kil (bland annat biblioteket, konserter och barnaktiviteter).",
    bandy: "Bandymatcher i Värmland från Svenska Bandyförbundets spelprogram i Profixio: seniorernas serier, cuper och träningsmatcher, till exempel IF Boltics hemmamatcher på Tingvalla. Bandy spelas på is med skridskor (inte innebandy).",
  };

  const section = (ico, title, ...content) => el("section", {}, el("h2", {}, icon(ico), title), ...content);

  function status(s) {
    if (!s.enabled) return el("span", { class: "status-off" }, "Avstängd");
    if (s.error) return el("span", { class: "status-err" }, "Fel");
    return el("span", { class: "status-ok" }, "OK");
  }

  window.renderAbout = () => {
    const m = state.meta || {};
    const sources = groupSources(m.sources);
    const chat = m.chat || {};
    const chatOn = chat.visible !== false;
    const features = chatOn ? FEATURES : FEATURES.flatMap(([ico, title, text]) =>
      ico in NO_CHAT_FEATURES ? (NO_CHAT_FEATURES[ico] ? [[ico, title, NO_CHAT_FEATURES[ico]]] : []) : [[ico, title, text]]);
    $("#about").replaceChildren(
      section("info", "Vad är Värmlandsinfo?",
        el("p", {}, chatOn
          ? "Värmlandsinfo samlar evenemang i Värmland från flera källor och visar dem på ett ställe: som lista, i en kalender och via en AI-assistent som svarar på frågor om vad som händer."
          : "Värmlandsinfo samlar evenemang i Värmland från flera källor och visar dem på ett ställe: som lista och i en kalender."),
        el("p", { class: "muted" }, `Just nu finns ${m.events?.length ?? "–"} aktuella evenemang. Alla källor hämtades senast ${fmtTime(m.completed)}. Varje källa hämtas en gång om dagen, vid en slumpad tid på förmiddagen.`)),

      section("sparkles", "Funktioner",
        el("div", { class: "features" }, features.map(([ico, title, text]) =>
          el("div", { class: "feature" }, icon(ico), el("h3", {}, title), el("p", {}, text))))),

      section("layers", "Källor",
        el("div", { style: "overflow-x:auto" }, el("table", { class: "src-table" },
          el("thead", {}, el("tr", {}, el("th", {}, "Källa"), el("th", {}, "Innehåll"), el("th", {}, "Evenemang"),
            el("th", {}, "Senast hämtad"), el("th", {}, "Status"))),
          el("tbody", {}, sources.map((s) => el("tr", {},
            el("td", {}, s.members.length > 1
              ? [el("strong", {}, s.title), el("div", { class: "muted", style: "font-size:.8rem" },
                  s.members.flatMap((m, i) => [i ? " och " : "", el("a", { href: m.homepage, target: "_blank", rel: "noopener" }, m.title)]))]
              : el("a", { href: s.homepage, target: "_blank", rel: "noopener" }, s.title)),
            el("td", {}, SOURCE_INFO[s.key] || ""),
            el("td", {}, s.enabled ? String(s.count) : "–"),
            el("td", {}, fmtTime(s.updated)),
            el("td", { title: s.error || s.config_error || "" }, status(s), s.error || s.config_error
              ? el("div", { class: "muted", style: "font-size:.8rem" }, s.error || s.config_error) : null))))))),

      !chatOn ? null : section("message", "AI-chatten",
        el("p", {}, "AI-chatten använder en språkmodell i din egen Ollama-server. För varje fråga tolkar appen tidsuttryck (idag, i helgen, nästa vecka, 3 oktober …), kommuner, evenemangstyper och sökord. Sedan skickar den de mest relevanta evenemangen till modellen, som instrueras att bara svara utifrån dem."),
        el("p", {}, "Modellen körs lokalt i ditt eget nätverk, så frågorna skickas aldrig till någon AI-tjänst i molnet. Det gör att svaren kan ta lite längre tid än hos molntjänster som ChatGPT och Gemini."),
        el("p", {}, "Webbsökning (valfritt): med en egen SearXNG-server kan AI:n komplettera svaren med information från webben, till exempel om en artist eller en plats. Frågan skickas då som sökord via SearXNG till sökmotorer på webben. Webbträffarna visas under svaret, och evenemangen i appen går alltid före. Det söks bara på webben när frågan gäller ett visst evenemang, en plats eller en arrangör i appen, aldrig för enkla sökfrågor och sparade svar."),
        el("p", {}, "AI:n svarar bara på frågor om evenemangen i appen och ger personliga rekommendationer, till exempel utifrån barns ålder. En spärr kontrollerar varje fråga innan AI:n och webbsökningen kopplas in. Frågor om något som inte finns i appen, till exempel ett nöjesfält i en annan stad, och frågor som inte rör evenemang alls får ett fast svar. Försök att ändra AI:ns uppdrag stoppas också."),
        el("p", {}, "Alla frågor behöver inte AI. Frågor som bara söker evenemang (när, var, vilka, vad händer …) besvaras direkt med en sökning bland evenemangen, sorterad efter datum. Det går snabbt och fungerar även utan Ollama. AI:n används när frågan kräver en bedömning: rekommendationer, jämförelser eller personliga önskemål som ålder och intressen."),
        el("p", {}, "Du kan ställa följdfrågor utan att upprepa dig, till exempel \"Vilken tid börjar den?\" eller \"Hur tar jag mig dit?\": AI:n får samtalets tidigare frågor och svar och de evenemang som svaren tog upp. Samtalet finns kvar om sidan laddas om och rensas när du trycker Nytt samtal eller lämnar sidan Fråga AI. Flera kan använda Fråga AI samtidigt, och varje flik har ett eget samtal på servern. Den lokala AI-modellen svarar på två frågor åt gången, och övriga ställs i kö. Du ser då din plats i kön. För att ingen ska kunna belasta AI:n får varje samtal ställa högst 5 frågor till AI:n per 30 minuter och varje adress högst 20. Frågor som besvaras direkt utan AI och sparade svar räknas inte, och när gränsen är nådd visas hur länge du behöver vänta."),
        el("p", {}, "Svaren sparas. Ställs samma fråga samma dag och evenemangen inte har ändrats, visas det sparade svaret direkt utan en ny förfrågan till AI:n. Alla fördefinierade frågor sparas, liksom de 10 senaste egna frågorna."),
        el("p", { class: "muted" }, chat.enabled ? `Modell: ${chat.model}. Webbsökning: ${chat.websearch ? "på" : "av"}.` : "AI-chatten är inte konfigurerad. Sätt OLLAMA_URL i .env för att aktivera den.")),

      section("database", "Cookies och lagring",
        el("p", {}, `Appen använder inga cookies och laddar inga externa skript, typsnitt eller spårning. ${chatOn ? "Tre" : "Två"} små värden sparas i din webbläsare för att gränssnittet ska fungera som du förväntar dig:`),
        el("ul", {},
          el("li", {}, el("strong", {}, "route"), " (localStorage): om du senast tittade på listan eller kalendern."),
          el("li", {}, el("strong", {}, "sidebar"), " (localStorage): om menyn är ihopfälld eller utfälld."),
          !chatOn ? null : el("li", {}, el("strong", {}, "chat-session"), " (sessionStorage): samtalets slumpmässiga id i Fråga AI. Det försvinner när fliken stängs.")),
        !chatOn ? el("p", {}, "Webbserverns åtkomstlogg är avstängd, så besökarnas IP-adresser sparas inte i loggen.")
          : el("p", {}, "Samtalen i Fråga AI (frågor och svar) sparas bara i serverns minne. Ett samtal tas bort direkt när du trycker Nytt samtal eller lämnar sidan Fråga AI. Samtal som inte använts på 2 timmar (till exempel när fliken stängts) tas bort vid nästa hämtning från källorna, och alla samtal tas bort när dagens hämtningar är klara och när appen startas om. Spärren för Fråga AI minns din IP-adress i minnet tills din senaste fråga till AI:n är 30 minuter gammal, och glömmer den vid nästa hämtning därefter. Webbserverns åtkomstlogg är avstängd, så besökarnas IP-adresser sparas inte i loggen."),
        el("p", {}, "Evenemangens bilder visas via appen. Servern hämtar dem från källorna och sparar dem, så din webbläsare kontaktar aldrig källornas bildservrar och de ser inte din IP-adress. Bilder som inte längre hör till något evenemang tas bort vid nästa hämtning från källorna."),
        el("p", {}, "Länkar till källorna skickar inte med att du kommer från Värmlandsinfo. Klickar du på en länk besöker du förstås källans webbplats, med de villkor som gäller där."),
        m.visit_stats ? el("p", {}, el("strong", {}, "Besöksstatistik: "),
          "den här installationen räknar besök på servern, utan cookies. Unika besökare räknas per dygn med en hash av IP-adress och webbläsare som inte kan följas mellan dygnen. Dagens besök sparas med IP-adress, ungefärlig plats (land och ort, som slås upp lokalt), enhet, webbläsare och vilken webbplats du kom från. När dygnet är slut summeras det och IP-adresserna tas bort. Den summerade statistiken sparas i 13 månader. Bara den som driftar appen kan se statistiken.") : null),

      section("shield", "Licens och ansvar",
        el("p", {}, "Värmlandsinfo är öppen källkod under ", el("a", { href: `${REPO}/blob/main/LICENSE`, target: "_blank", rel: "noopener" }, "MIT-licensen"),
          ". Du får använda, kopiera, ändra och dela koden fritt, så länge licenstexten följer med."),
        el("p", {}, el("strong", {}, "Källornas innehåll: "),
          "appen gör inga anspråk på innehållet från källorna. Texter, bilder och uppgifter om evenemangen tillhör respektive källa och upphovsperson (",
          sources.flatMap((g) => g.members).flatMap((x, i, all) => [i ? (i === all.length - 1 ? " och " : ", ") : "",
            x.homepage ? el("a", { href: x.homepage, target: "_blank", rel: "noopener" }, x.title) : x.title]),
          "). Appen visar ett urval och länkar till källan för varje evenemang. Kontrollera alltid tider och andra uppgifter hos arrangören eller källan."),
        el("p", {}, el("strong", {}, "API:t: "),
          "API:t är till för appens eget gränssnitt och har ingen öppen dokumentation. Status och manuell uppdatering (/api/health och /api/refresh) svarar bara inom det lokala nätverket, aldrig via internet eller en omvänd proxy."),
        el("p", {}, el("strong", {}, "Inget ansvar: "),
          "appen levereras i befintligt skick, utan garantier av något slag. Inget som helst ansvar tas för appens funktion, för att uppgifterna stämmer eller är aktuella, för AI-chattens svar eller för följderna av att använda appen.")),

      section("sparkles", "Framtagen med Claude Code",
        el("p", {}, "Värmlandsinfo är framtagen med hjälp av ", el("a", { href: "https://claude.com/claude-code", target: "_blank", rel: "noopener" }, "Claude Code"),
          ", Anthropics AI-assistent för programmering. Idéer, krav och beslut kommer från projektets ägare. Claude Code har skrivit det mesta av koden, testerna och dokumentationen, och arbetar efter issues på GitHub, kör testerna och följer upp bygg och releaser."),
        el("p", {}, chatOn
          ? "Claude används bara för att utveckla appen. AI-chatten i appen använder en egen Ollama-server, och inga frågor skickas till Claude eller någon annan AI-tjänst i molnet."
          : "Claude används bara för att utveckla appen, och appen skickar inget till Claude eller någon annan AI-tjänst i molnet.")),

      section("code", "Version och källkod",
        el("p", {}, `Du kör version ${m.version ? "v" + m.version : "–"}. Appen är öppen källkod under MIT-licensen. Ändringar, versioner och instruktioner finns på GitHub.`),
        el("div", { class: "actions" },
          m.release_url ? ext(m.release_url, `Release v${m.version}`, "btn btn-primary") : null,
          ext(`${REPO}/blob/main/CHANGELOG.md`, "Ändringslogg"),
          ext(REPO, "Källkod på GitHub", "btn", "code"))),
    );
  };
})();
