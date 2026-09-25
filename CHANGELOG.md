# Changelog

Alla viktiga ändringar i projektet dokumenteras här.
Formatet följer [Keep a Changelog](https://keepachangelog.com/sv/1.1.0/) och projektet använder
[semantisk versionering](https://semver.org/lang/sv/).

## [Unreleased]

## [0.17.0] - 2026-09-25

### Ändrat
- Fråga AI och webbsökningen gäller bara evenemangen i appen. En spärr stoppar andra frågor innan SearXNG eller Ollama
  anropas: frågor som nämner något som inte finns i appen (t.ex. Liseberg) och frågor som inte rör evenemang. Webben
  söks bara när frågan nämner ett evenemang, en plats eller en arrangör i appen (#48)

## [0.16.0] - 2026-09-25

### Tillagt
- Fråga AI kan söka på webben via en egen SearXNG (`SEARXNG_URL`, `SEARXNG_RESULTS`, `SEARXNG_LANGUAGE`). AI-frågor får
  webbträffarna som extra underlag, och svaren visar dem under *Från webben*. Evenemangen i appen går före webben, och
  direktsökningar och sparade svar söker aldrig på webben (#46)

### Dokumentation
- Nya skärmdumpar i README för den aktuella versionen, med källan Loppisar, filtret Loppis och webbsökning (#47)

## [0.15.0] - 2026-09-25

### Ändrat
- Karlstad Loppis och loppisar.com visas som en källa, *Loppisar*, i menyn, i filtret Källa, på korten och på sidan
  Om applikationen. I bakgrunden är de fortfarande två källor med egen hämtning och status (#45)

## [0.14.0] - 2026-09-25

### Ändrat
- Loppisar är ett eget filter, *Loppis*, direkt efter *Gratis*. Loppisar bryts ut ur Visit Värmlands kategori
  "Marknad, mässa, auktion och loppis", som nu heter "Marknad, mässa och auktion". Fråga AI förstår loppis som
  en egen typ (#44)

## [0.13.0] - 2026-09-25

### Tillagt
- Ny källa: Karlstad Loppis. Bakluckeloppisen på I2 Norra Fältet i Karlstad visas med nästa datum, söndagar 10–15 (#43)
- Ny källa: loppisar.com. Loppisar i Värmland med öppettider per dag, 30 dagar framåt. Ordet "loppis" räknas inte
  vid sammanslagning av dubbletter, så att olika loppisar samma dag inte slås ihop (#43)

## [0.12.0] - 2026-09-25

### Ändrat
- Ingen gammal data sparas efter morgonkörningen. Efter den dagliga hämtningen, och vid start, tas källdata från före
  morgonkörningen bort, liksom data från avstängda källor, inaktuella AI-svar, gårdagens chattsamtal och kvarglömda
  temporära filer. En källa som fallerar på morgonen får först två nya försök (#42)

### Rättat
- Data från en avstängd källa (till exempel Ticketmaster utan API-nyckel) visades fortfarande om filen fanns kvar (#42)

### Dokumentation
- README visar skärmdumpar av lista, kalender, Fråga AI och mobilvy, och är uppdaterad med de senaste
  ändringarna. Skriptet `tools/readme-screenshots.mjs` skapar skärmdumparna (#41)

## [0.11.0] - 2026-09-24

### Tillagt
- Ny källa: Great Event of Karlstad (sidan Kommande evenemang). Den ger konserter och evenemang på bland annat Löfbergs
  Arena, Nöjesfabriken och Julins Backyard BBQ. Backyard Live Music blir ett evenemang per artist och datum (#40)

## [0.10.0] - 2026-09-24

### Ändrat
- Kommun och Källa är flervalslistor, så det går att välja till exempel Karlstad och Hammarö samtidigt. Reglaget
  "Visa varje tillfälle" heter nu "Ett kort per datum" och har en förklarande hjälptext. Filtren får bättre plats
  på mellanstora skärmar (#39)

## [0.9.0] - 2026-09-24

### Tillagt
- Sessionstyrning i Fråga AI för flera samtidiga användare:
  - varje flik har ett eget samtal på servern, och klienten skickar bara sin nya fråga
  - samtalet finns kvar vid omladdning
  - en fråga i taget och högst 10 per minut per samtal
  - rättvis kö till Ollama som visar platsen i kön (#38)

## [0.8.0] - 2026-09-24

### Ändrat
- Fråga AI besvarar enkla sökfrågor ("När spelar Färjestad nästa gång?", "Vad händer idag?") direkt med en
  sökning bland evenemangen, i datumordning och utan AI. AI:n används bara för frågor som kräver en bedömning,
  som rekommendationer och personliga önskemål. Direktsökningen fungerar även utan Ollama (#37)

## [0.7.0] - 2026-09-24

### Tillagt
- Sidomenyn kan fällas ihop till en smal list med ikoner på datorn. Valet sparas i webbläsaren (#35)
- Fråga AI ger personliga rekommendationer: ålder och familjeord ("min 8 år gamla son") tolkas som barn,
  barn- och familjeevenemang prioriteras och AI:n motiverar 3–5 förslag (#36)

### Säkerhet
- Fråga AI svarar bara på frågor om appens evenemang och aktiviteter. Andra frågor får ett fast svar från
  servern (modellens markör fångas innan något visas), försök att ändra AI:ns uppdrag stoppas utan att
  modellen tillfrågas, evenemangsdata skickas avgränsad och rensad (skydd mot prompt injection), frågor
  begränsas till 1000 tecken och högst 2 frågor körs samtidigt mot Ollama (#36)

## [0.6.0] - 2026-09-24

### Tillagt
- AI-svar sparas i `data/chat_cache.json`. Samma fråga samma dag, mot samma evenemangsdata och modell,
  besvaras direkt utan ny förfrågan till AI:n. Fördefinierade frågor sparas alltid, egna frågor de 10
  senaste. Följdfrågor sparas inte. De fördefinierade frågorna definieras på servern (`/api/chat/presets`),
  och en ny finns: *Gratis* (#33)

### Borttaget
- Ikonen och rubriken "Evenemang"/"Kalender" ovanför filtren. Antalet evenemang visas diskret ovanför
  listan (#34)

## [0.5.0] - 2026-09-24

### Tillagt
- Fråga AI informerar om att AI:n körs lokalt och att svaren kan ta längre tid än hos molntjänster som
  ChatGPT och Gemini. Ett vänteläge visas tills svaret börjar komma (#32)
- CI kontrollerar syntaxen i gränssnittets JavaScript (#31)

### Borttaget
- Knappen *Uppdatera evenemang* i menyn. Den dagliga uppdateringen finns kvar, och en manuell uppdatering
  görs med `POST /api/refresh` (#31)

## [0.4.0] - 2026-09-24

### Ändrat
- Platslänkarna går till Google Maps i stället för OpenStreetMap. Platser utan koordinater (t.ex.
  Karlstad CCC, Scalateatern och Löfbergs Arena) får nu också en kartlänk via sökning på namn och ort (#30)

## [0.3.0] - 2026-09-24

### Tillagt
- Sidan *Om applikationen* beskriver funktionerna och visar källornas status, AI-modell och version (#26)
- Datumval med färdiga intervall: Idag, Imorgon, I helgen, Den här veckan, Nästa vecka, Den här
  månaden, Nästa månad eller egna datum (#27)
- Kategorin *Gratis* för evenemang med fri entré, baserad på källornas prisuppgifter. Den finns som
  filterchip och etikett, och Fråga AI förstår "gratis" och "fri entré" (#29)

### Ändrat
- Nytt, modernare utseende: sidomeny med navigering, uppdateringsknapp och källor. Egen adress per vy,
  SVG-ikoner, nya knappar och en ordnad filterpanel. Utfällbar meny och kategorier som sveps i sidled
  på mobil (#27)
- *Fråga AI* är en egen sida med förslagskort, snabbval, modellstatus och ett nytt inmatningsfält (#27)
- Den permanenta statustexten är borttagen. "Uppdaterad" visas i stället bredvid versionen i menyn, och
  meddelanden visas bara när något händer (#28)

## [0.2.1] - 2026-09-24

### Rättat
- Efter uppgradering kunde webbläsaren, eller en proxy/cache framför appen, fortsätta visa gammal
  stilmall och gammalt skript. Stil, skript och ikoner refereras nu med versionen i adressen
  (`?v=X.Y.Z`), `index.html` skickas med `Cache-Control: no-cache` och API-svaren cachas inte (#25)

## [0.2.0] - 2026-09-24

### Tillagt
- Versionen visas i sidhuvudet och sidfoten som länk till releasen på GitHub, och skrivs ut tydligt
  med länkar i loggen när containern startar (#24)
- Kontrastkontroll (`tools/contrast-check.mjs`) som mäter all text i ljust och mörkt läge (#23)

### Rättat
- Webbsidan är lättläst i både ljust och mörkt läge: all text klarar WCAG AA. Kategorietiketter och
  valda filter visar vanlig text på en ton av kategorifärgen. Kalendern tonar inte längre ned text med
  genomskinlighet. Accentfärgade element och felmeddelanden har rätt textfärg i mörkt läge, och
  webbläsarens egna kontroller följer temat (#23)
- Sidhuvudet var svårläst (vit text på ljusgrön bakgrund). Det har nu en fast mörkgrön bakgrund och
  vita knappar med mörk text, med kontrast över 9:1 (#22)

## [0.1.0] - 2026-09-24

### Tillagt
- Stöd för flera evenemangskällor. Samma evenemang från flera källor slås ihop till ett, med länkar
  till alla källor. Status per källa och ett källfilter i gränssnittet (#16)
- Ticketmaster som källa (kräver `TICKETMASTER_API_KEY`) (#17)
- Färjestads hemmamatcher från SHL:s spelschema, med exakta tider (#18)
- Karlstad CCC som källa (#20)
- Scalateatern som källa (#21)

### Ändrat
- Karlstads och Hammarö kommuns evenemangskalendrar täcks av Visit Värmland, som de hämtar sina
  evenemang från (#19)
- Rådata sparas per källa i `data/`. Befintlig `visitvarmland.json` läses utan ny hämtning (#16)

## [0.0.2] - 2026-09-24

### Ändrat
- Images publiceras bara vid release. `edge`-imagen från `main` är borttagen (#13)
- Ändringar committas direkt på `main`. Tester och Docker-bygge körs vid varje push som kontroll (#15)

## [0.0.1] - 2026-09-24

Första releasen.

### Tillagt
- Översikt över aktuella evenemang i Värmland från Visit Värmlands API, i datumordning med
  kategori och beskrivning av typen, bilder, länkar och filter (#1)
- AI-chatt kopplad till Ollama för frågor om evenemangen, med strömmade svar,
  följdfrågor och länkar till underlaget (#2)
- Knappen "Uppdatera evenemang" och daglig schemalagd uppdatering (`DAILY_REFRESH_TIME`) (#3)
- Versionsnummer i gränssnittet och i `/api/health`, CHANGELOG, CI och ett releaseflöde som
  skapar en GitHub-release och publicerar imagen på ghcr.io (#4)
- Releasen skapas automatiskt när en ny version når `main` (#11)
- `.env.example` med alla inställningar
- Hämtad data sparas utanför containern i `./data` (volym `/data`). Vid omstart laddas den direkt
  och API:et anropas bara när datan är inaktuell (#7)
- `PUID`/`PGID` styr vem som äger filerna i datakatalogen (#7)
- Kalendervy med en vecka per rad och veckonummer. Klick på en dag visar dagens evenemang, och
  samma filter som i listan gäller (#8)
- Skydd för Visit Värmlands API: knappen hämtar högst var 5:e minut, `REFRESH_MINUTES` är minst 30,
  takten anpassas efter API:ets kvot, kommunlistan hämtas en gång per vecka och ett misslyckat
  försök görs om efter 30 minuter (#9)
- Egen ikon och logga (en sol inspirerad av Solstaden Karlstad), favicon och webbappmanifest så att
  appen kan läggas till på hemskärmen (#10)

### Ändrat
- Standardport på värden är nu 7799 (#5)
- Containern startar som root bara för att ge `/data` rätt ägare och kör sedan appen som
  `PUID:PGID` (tidigare en fast användare med uid 10001) (#7)

### Rättat
- `REFRESH_MINUTES=0` gav en evig hämtloop i den första versionen. Nu betyder 0 alltid "av" (#9)

[Unreleased]: https://github.com/tubalainen/varmlandsinfo/compare/v0.17.0...HEAD
[0.17.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.12.0...v0.13.0
[0.12.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/tubalainen/varmlandsinfo/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.0.2...v0.1.0
[0.0.2]: https://github.com/tubalainen/varmlandsinfo/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/tubalainen/varmlandsinfo/releases/tag/v0.0.1
