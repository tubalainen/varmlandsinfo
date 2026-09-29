# Changelog

Alla viktiga ändringar i projektet dokumenteras här.
Formatet följer [Keep a Changelog](https://keepachangelog.com/sv/1.1.0/) och projektet använder
[semantisk versionering](https://semver.org/lang/sv/).

## [Unreleased]

## [0.28.2] - 2026-09-29

### Dokumentation
- Arkitekturbilden visar 13 källor (med Säffle och Kil), och hänvisningarna till koden pekar på dagens rader (#80).

## [0.28.1] - 2026-09-29

### Rättat
- Filtret Kommun visar bara kommuner, inte orter som Väse och Brunskog eller orter utanför området som Stockholm.
  Orter och postnummer knyts till sin kommun, så att fler evenemang får rätt kommun (t.ex. Karlskoga Konserthall),
  och Fråga AI förstår frågor om orter (#81).

## [0.28.0] - 2026-09-29

### Tillagt
- Två nya källor, som visas som en källa, *Kommunerna*: Säffles och Kils egna evenemangskalendrar, med evenemang som
  inte finns hos Visit Värmland (till exempel Medis, Sagabiografen och biblioteken). Säffle hämtas med ett anrop och
  Kil med ett eller två (#79).

### Ändrat
- När samma evenemang finns i flera källor fylls kommunen i från en annan källa om den första saknar den (#79).

### Dokumentation
- CLAUDE.md beskriver att grenar inte kan tas bort från Claudes molnmiljö och hur städningen görs i stället (#78).

## [0.27.0] - 2026-09-29

### Ändrat
- Mycket försiktiga nya försök mot källorna, så att appen aldrig riskerar att bli spärrad: vid 429 och serverfel
  (5xx) högst ett nytt försök, aldrig tidigare än källan ber om (`Retry-After`) och aldrig om den ber om mer än 60
  sekunder. Serverfel väntar 60 sekunder i stället för 5. En källa som nekar åtkomst (401/403) pausas till nästa
  morgonkörning. Försöken var 30:e minut efter en misslyckad hämtning är borttagna, och morgonkörningens två nya
  försök görs med 15 minuters mellanrum i stället för 5 (#76).

### Borttaget
- Snabbvalen ovanför inmatningsfältet i Fråga AI är borttagna. Förslagskorten finns kvar (#77).

## [0.26.0] - 2026-09-29

### Ändrat
- Svarar en källa med ett tillfälligt serverfel (HTTP 500–599) görs ett nytt försök efter 5 sekunder, i stället för
  att källan direkt markeras med fel (#75).

## [0.25.1] - 2026-09-29

### Rättat
- Bandy: källan gav 0 matcher (och filtret Bandy saknades) när Profixio svarade på svenska, vilket det gör från en
  server i Sverige. Tolkningen klarar nu både svenska och engelska, källan begär svenska, och matcher som inte går att
  tolka ger ett tydligt fel i stället för 0 matcher (#74).

## [0.25.0] - 2026-09-29

### Ändrat
- Fråga AI har sammanhang i samtalet: följdfrågor som syftar tillbaka ("Vilken tid börjar den?", "Var ligger
  arenan?") besvaras av AI:n med samtalets historik och evenemangen från de senaste svaren först i underlaget, i
  stället för med en ny sökning utan sammanhang. Utan Ollama visas förra svarets evenemang igen. Samtalet rensas
  när man trycker Nytt samtal eller lämnar sidan Fråga AI, och en pågående fråga avbryts då (#73).

## [0.24.0] - 2026-09-29

### Tillagt
- Ny källa Bandy: Svenska Bandyförbundets matcher i Profixio som spelas i Värmland, för seniorer (serier, cuper och
  träningsmatcher), till exempel IF Boltics hemmamatcher i Bandyallsvenskan på Tingvalla (#72).
- Inställningen `CHAT_ENABLED` (standard `true`): med `false` döljs Fråga AI helt, med menyval, sida, texter på sidan
  Om och API:t för chatten (#69).
- Snabbfiltret Bandy: bandymatcher får en egen kategori (titeln nämner bandy, inte innebandy), som följer med vid
  sammanslagning, och snabbvalet Bandy i Fråga AI (#70).
- Snabbfiltret SHL: Färjestads hemmamatcher får en egen kategori, även när matchen också finns hos Visit Värmland
  eller Ticketmaster, och snabbvalet SHL i Fråga AI (#68).

### Ändrat
- Bandy och innebandy hålls isär: sökrutan hittar inte innebandy när man söker på bandy, och i Fråga AI ger sökord
  som inte finns i något evenemang svaret "inga evenemang" i stället för alla evenemang. "här" räknas inte längre
  som sökord (#71).
- Beskrivningen under "Beskrivning och bilder" är lättare att läsa: långa textmassor delas i stycken vid
  meningsgränser, med behaglig radlängd och radavstånd. Webb- och e-postadresser blir länkar, och sammanfattningen
  upprepas inte när beskrivningen är utfälld. Ticketmasters sammanfattning klipps vid ett ordslut (#67).

### Dokumentation
- Skärmdumparna i README och `docs/` är tagna om (filtren SHL och Bandy), och arkitekturbilden visar elva källor
  (#72).

## [0.23.0] - 2026-09-29

### Tillagt
- Besöksstatistik på den dolda sidan `/besoksinfo`, skyddad med lösenordet `BESOKSINFO_PASSWORD` (av som standard):
  unika besökare per dygn utan cookies, sidvisningar, land och ort (DB-IP:s fria databas, uppslagen lokalt), enhet,
  webbläsare, operativsystem och hänvisning, samt dagens besökare med IP-adress. IP-adresserna tas bort när dygnet är
  slut, och den summerade statistiken sparas i 13 månader (#66)

### Dokumentation
- Arkitekturbild skapad med Archify i README och i `docs/arkitektur.md`, med diagrammets källa och ett interaktivt
  diagram i `docs/arkitektur/` (#63)
- Arkitekturbilden länkar till den interaktiva, animerade översikten på GitHub Pages, som i reforger-server-manager
  (#64)
- Arkitekturbilden visar gränsen för Docker-containern (#65)

## [0.22.0] - 2026-09-29

### Ändrat
- Evenemangens bilder visas via appen (`/img/…`), så att källornas bildservrar aldrig ser besökarna. Bilderna hämtas
  på serversidan första gången de visas och sparas i `data/images/`. Bara bilder som finns i evenemangen, bara
  publika värdar och bara riktiga bilder släpps igenom. Sidan tillåter bara bilder från appen själv, och länkar till
  källorna skickar inte med att besökaren kommer från appen (#60)
- All lagrad data rensas när den blir inaktuell, i samband med varje hämtning från källorna (även `POST /api/refresh`)
  och vid start: även utgångna chattsamtal, IP-adresser i spärren för Fråga AI och halvfärdiga bildfiler.
  Webbserverns åtkomstlogg är avstängd, så besökarnas IP-adresser hamnar inte i loggen, och Dockers logg roteras
  (3 filer à 10 MB) (#62)

### Dokumentation
- Kortfattad README, och detaljerna i `docs/`: installation, funktioner, källor, Fråga AI, data och integritet, API
  och utveckling (#61)

## [0.21.0] - 2026-09-29

### Ändrat
- Spärrarna i Fråga AI gäller bara frågor som går till AI:n. Sökfrågor, sparade svar och stoppade frågor räknas
  inte (#57)
- Högst 5 frågor till AI:n per 30 minuter och samtal (tidigare 10 frågor av alla slag per minut) och 20 per
  30 minuter och IP-adress (tidigare 20 per minut). Meddelandet säger hur länge man behöver vänta (#58)

### Dokumentation
- Sidan Om applikationen och README beskriver vad som lagras hos besökaren: inga cookies, tre små värden i
  webbläsarens lagring, samtalen bara i serverns minne, och att bilderna hämtas från källornas bildservrar (#59)

## [0.20.0] - 2026-09-29

### Säkerhet
- Begränsad åtkomst till API:t: FastAPI:s `/docs`, `/redoc` och `/openapi.json` är avstängda, `/api/health` och
  `/api/refresh` svarar bara inom det lokala nätverket (aldrig via omvänd proxy), och Fråga AI har en spärr på
  20 frågor per minut och IP-adress utöver spärren per session (#56)

## [0.19.1] - 2026-09-29

### Ändrat
- Sidan Om applikationen visar licensen (MIT), att appen inte gör anspråk på källornas innehåll, att inget ansvar
  tas för appens funktion och att appen är framtagen med hjälp av Claude Code (#55)

### Dokumentation
- MIT-licens (`LICENSE`), och README beskriver licensen, att appen inte gör anspråk på källornas innehåll, att
  inget ansvar tas för appens funktion och att appen är framtagen med hjälp av Claude Code (#54)

## [0.19.0] - 2026-09-29

### Tillagt
- Nya kategorier ur ordregler i titel och ingress: Film, Spel och quiz, Träffar och caféer samt Böcker och
  litteratur. Konserter som saknar kategorin Musik (t.ex. gospel och körer) får den. Fråga AI känner igen de nya
  kategorierna (#53)

### Ändrat
- Under varje dag visas evenemang som bara äger rum en dag först, före utställningar och andra evenemang med flera
  datum. Gäller både listan och kalendern (#52)
- Tydligare kategorifilter i bokstavsordning: Visit Värmlands Evenemang och Övriga evenemang blir Övrigt, som bara
  visas när ingen annan kategori passar, och Motor heter Motorträffar så att den inte förväxlas med Motorsport (#53)

## [0.18.1] - 2026-09-27

### Rättat
- Motorsport: rallyn och andra tävlingar som utgår från en by i Värmland (t.ex. Finnskogsvalen på Vitsand) sorterades
  bort när klubbnamnet saknade kommun. Fler orter i Värmland känns nu igen (#51)

### Dokumentation
- Nya skärmdumpar i README med källan och filtret Motorsport, och CLAUDE.md beskriver läget, användarens beslut och
  lärdomar från utvecklingsmiljön (#50)

## [0.18.0] - 2026-09-27

### Tillagt
- Ny källa Motorsport: tävlingar och prova på-dagar i Värmland och Karlskoga från Svensk Bilsports tävlingskalender
  (LoTS: folkrace, rally, rallycross, crosskart, karting …) och Svemo TA (motocross, enduro, speedway …). Läget
  avgörs av banans namn och arrangörens ort. Ny filterkategori *Motorsport*, och *Motor* gäller nu motorträffar och
  fordonsutställningar. Dubbletter mot Visit Värmland slås ihop även när titlarna skiljer sig och när tävlingen
  pågår flera dagar. Fråga AI förstår motorsport och har ett nytt snabbval (#49)

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

[Unreleased]: https://github.com/tubalainen/varmlandsinfo/compare/v0.28.2...HEAD
[0.28.2]: https://github.com/tubalainen/varmlandsinfo/compare/v0.28.1...v0.28.2
[0.28.1]: https://github.com/tubalainen/varmlandsinfo/compare/v0.28.0...v0.28.1
[0.28.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.27.0...v0.28.0
[0.27.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.26.0...v0.27.0
[0.26.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.25.1...v0.26.0
[0.25.1]: https://github.com/tubalainen/varmlandsinfo/compare/v0.25.0...v0.25.1
[0.25.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.24.0...v0.25.0
[0.24.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.23.0...v0.24.0
[0.23.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.22.0...v0.23.0
[0.22.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.21.0...v0.22.0
[0.21.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.20.0...v0.21.0
[0.20.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.19.1...v0.20.0
[0.19.1]: https://github.com/tubalainen/varmlandsinfo/compare/v0.19.0...v0.19.1
[0.19.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.18.1...v0.19.0
[0.18.1]: https://github.com/tubalainen/varmlandsinfo/compare/v0.18.0...v0.18.1
[0.18.0]: https://github.com/tubalainen/varmlandsinfo/compare/v0.17.0...v0.18.0
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
