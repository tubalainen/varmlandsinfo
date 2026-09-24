# Changelog

Alla viktiga ändringar i projektet dokumenteras här.
Formatet följer [Keep a Changelog](https://keepachangelog.com/sv/1.1.0/) och projektet använder
[semantisk versionering](https://semver.org/lang/sv/).

## [Unreleased]

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

[Unreleased]: https://github.com/tubalainen/varmlandsinfo/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.0.2...v0.1.0
[0.0.2]: https://github.com/tubalainen/varmlandsinfo/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/tubalainen/varmlandsinfo/releases/tag/v0.0.1
