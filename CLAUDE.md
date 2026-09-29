# Värmlandsinfo – instruktioner för Claude

Dockerbaserad webbapp (FastAPI + statisk HTML/JS) som visar evenemang i Värmland från flera källor (Visit Värmland
m.fl.), med AI-chatt via Ollama. Användaren kommunicerar på svenska: skriv issues, PR:er, commits och svar på svenska.
Detta dokument är också projektets minne mellan sessioner: håll avsnitten **Läget**, **Beslut** och **Lärdomar**
aktuella när något ändras.

## Arbetsflöde (ska alltid följas)

1. **Issue först.** Varje förändring kopplas till en GitHub-issue. Finns ingen, formulera en med
   bakgrund, krav och acceptanskriterier innan arbetet börjar. Issuen är baslinjen för förändringen.
2. **Direkt på `main`.** Committa och pusha ändringar direkt till `main` (användaren har uttryckligen
   bett om det). Inga arbetsgrenar eller PR:er. Commit-meddelandet refererar issuen, t.ex.
   `Kalendervy (#8)` med `Closes #8` i brödtexten.
3. **Grönt före push.** Kör testerna lokalt (`python -m pytest -q tests`) innan push. Efter push ska CI
   (`ci.yml`) och Docker-bygget (`docker-publish.yml`) vara gröna på `main`. Blir något rött, åtgärda direkt.
4. **CHANGELOG.** Lägg till en rad per ändring under `## [Unreleased]` i `CHANGELOG.md`, med issue-nummer.
5. **Release bara på användarens kommando.** En release kan innehålla flera ändringar.
   - **Versionen räknas fram automatiskt** (om användaren inte anger en) enligt semver utifrån
     `[Unreleased]` i CHANGELOG: nya funktioner eller ändrat beteende i appen ger MINOR (0.0.1 → 0.1.0),
     buggfixar och ändringar i bygg eller dokumentation ger PATCH (0.1.0 → 0.1.1), och brytande
     ändringar efter 1.0 ger MAJOR.
   - Gör en release-commit direkt på `main` som sätter versionen i `app/version.py` och flyttar
     `[Unreleased]` i `CHANGELOG.md` till `## [X.Y.Z] - ÅÅÅÅ-MM-DD`, med uppdaterade jämförelselänkar
     längst ner. Commit-meddelande: `Release vX.Y.Z`.
   - `release.yml` ser att versionen på `main` saknar release och skapar taggen `vX.Y.Z`,
     GitHub-releasen (CHANGELOG-avsnittet plus genererade notes) och imagen
     `ghcr.io/tubalainen/varmlandsinfo:X.Y.Z` / `X.Y` / `latest`.
   - Vänta in flödet **Release** (båda jobben) och rapportera länken till releasen.
   - Obs: taggar kan inte pushas från Claudes molnmiljö, och manuell körning av flöden nekas. Release
     via push till `main` är därför vägen. Höj aldrig versionen utan att användaren bett om en release.
6. **Ingen `edge`.** Images publiceras bara vid release.
7. **Städa efter varje release.** När releasen är klar och flödet **Release** är grönt:
   - inga öppna PR:er eller kvarglömda grenar (utöver `main`) ska finnas
   - alla issues som ingår i releasen är stängda (`completed`), och övriga inaktuella issues stängs
     med motivering (`not_planned`)
   - inga väntande påminnelser eller bevakningar ligger kvar
   - rapportera kort vad som städats

## Utveckling

- Tester: `pip install -r requirements-dev.txt && python -m pytest -q tests`
- Köra lokalt: `cd app && DATA_DIR=/tmp/data uvicorn main:app --port 8080`
- Docker: `docker compose up -d --build`. Porten på värden är 7799.
- Inställningar finns i `.env` (mall: `.env.example`). Nya inställningar ska in i `.env.example`,
  `docker-compose.yaml` och `docs/installation.md` (de viktigaste även i README).
- **Gränssnittet ska fungera i både ljust och mörkt läge.** Använd färgvariablerna i `style.css`
  (`--text`, `--muted`, `--accent`, `--on-accent`, `--danger` …) och aldrig fast vit text på färgad
  bakgrund. Kör `node tools/contrast-check.mjs` mot en körande app efter ändringar i gränssnittet. Den
  ska rapportera "Inga kontrastproblem". Granska även skärmdumparna i `tools/screenshots/`.
- **Checka aldrig in privata adresser** (t.ex. användarens Ollama-IP) eller `.env`.
- Var snäll mot källorna (Visit Värmland: 60 anrop/minut; Ticketmaster: 5/sekund och 5000/dygn;
  CCC, Scalateatern, Great Event, Karlstad Loppis, loppisar.com, SBF:s LoTS och Svemo TA är vanliga webbplatser).
  Svemo TA har 13 000+ historiska tävlingar: bläddra aldrig igenom hela listan, bara sista sidorna bakåt.
  Hämta inte oftare än nödvändigt, varken i appen eller under utveckling. Testa mot sparad data (se Lärdomar).
- Nycklar (t.ex. `TICKETMASTER_API_KEY`) får aldrig loggas eller synas i felmeddelanden. httpx-loggningen
  är därför avstängd.

## Struktur

- `app/sources/`: en modul per källa med `fetch()` (rådata) och `normalize()` (appens format).
  Ordningen i `sources/__init__.py` är prioritet vid sammanslagning
- `app/events.py`: hämtning, lagring (`/data/<källa>.json`) och status per källa
- `app/merge.py`: sammanslagning av samma evenemang från flera källor
- `app/common.py`: HTTP med rate limit (felmeddelanden utan frågesträng, alltså utan API-nycklar)
- `app/chat.py`: urval av evenemang, fördefinierade frågor och Ollama-anrop. `app/chat_cache.py`: sparade
  AI-svar (`/data/chat_cache.json`). `app/sessions.py`: samtal i Fråga AI (en session per flik, historiken på
  servern, bara i minnet, så appen ska köras som en process). `app/websearch.py`: valfri webbsökning via SearXNG
  för AI-frågor
- `app/main.py`: FastAPI-rutter, schemaläggning och städning (`cleanup`). `app/access.py`: vad som bara får anropas
  lokalt och spärren per IP. `app/images.py`: bilderna via appen (`/img/<nyckel>`). `app/visits.py`,
  `app/besoksinfo.py` och `app/geoip.py`: besöksstatistiken och den dolda sidan `/besoksinfo`
- `app/static/`: gränssnittet. `app.js` sköter navigering (`#/lista`, `#/kalender`, `#/fraga`, `#/om`), filter
  och lista, `calendar.js` kalendern, `chat.js` Fråga AI, `about.js` Om applikationen och `icons.js`
  SVG-ikonerna. Nya funktioner ska beskrivas på sidan Om applikationen (`about.js`)

## Läget (v0.23.0, 2026-09-29)

- **Källor** (`app/sources/`, prioritetsordning): Visit Värmland (API), Ticketmaster (API, kräver nyckel, av som
  standard), Karlstad CCC, Scalateatern, SHL (Färjestads hemmamatcher), Great Event, Karlstad Loppis + loppisar.com
  (grupp **Loppisar**), SBF/LoTS + Svemo TA (grupp **Motorsport**, `sources/motorsport.py`). En källas `group` gör att
  flera källor visas som en i gränssnittet (menyn, filtret Källa, korten, sidan Om), medan hämtning, lagring och status
  i `/api/health` är per källa.
- **Motorsport:** publika tävlingar och prova på-dagar i Värmland + Karlskoga. Läget avgörs av banans namn (`PLACES`
  i `motorsport.py`) och i andra hand arrangörens ort. Nya banor och byar läggs till i `PLACES` (rallyn har ofta
"Tillfällig" som bana och utgår från en by), men kontrollera först mot sparad SBF-data att ordet inte träffar banor
utanför området. motorsportivarmland.nu undersöktes som rallykälla (#51) men är en nyhetssajt utan strukturerad
kalender, och SBF har redan rallyna. LoTS och Svemo är ASP.NET/Telerik:
  sidbyte med postback (`__VIEWSTATE` + `__EVENTTARGET` från knappen med title "Next/Previous/Last Page").
- **Kategorier** (`categories.py`, regler i `common.finalize`): `SOURCE_NAMES` byter källornas namn (Visit Värmlands
  *Evenemang* och *Övriga evenemang* blir *Övrigt*, *Motor* blir *Motorträffar*). `split_loppis` bryter ut *Loppis* ur
  marknadskategorin, och `split_motorsport` ger tävlingar *Motorsport*, medan *Motorträffar* bara gäller träffar och
  fordonsutställningar. Sist lägger `refine` till kategorier ur ordregler (`KEYWORD_RULES`: Musik, Film, Spel och quiz,
  Träffar och caféer, Böcker och litteratur) från titeln, och från ingressen bara när källan saknar egen typ. Reglerna
  gäller inte loppisar och motorsport. *Övrigt* blir kvar bara när inget annat passar (Gratis räknas inte).
  Kategorifiltren står i bokstavsordning. Nya ordregler: pröva först mot sparad data så att de inte träffar fel.
  *SHL* (#68) sätts av källan SHL, *Bandy* (#70) av ordregeln (bara ordet bandy, inte innebandy eller bandyplanen). Kategorier i `categories.SOURCE_ONLY` följer med vid sammanslagning (`merge._absorb`),
  eftersom Visit Värmland och Ticketmaster har högre prioritet och annars skulle ta bort dem.
- **Ordning i listan och kalendern** (`multiDay` i `app.js`): under varje dag står evenemang som bara äger rum en dag
  före dem med flera datum (utställningar och återkommande evenemang lagras oftast som ett tillfälle per dag, inte
  som ett tillfälle över flera dagar), sedan tid och titel.
- **Sammanslagning** (`merge.py`): samma dag (varje dag i perioder ≤ 7 dagar), samma kommun och liknande titlar, eller
  `same_race` för motorsport med olika titlar. "loppis" och "konsert" m.fl. räknas inte som gemensamma ord.
- **Beskrivningen** i korten (`descriptionBlock` i `app.js`, #67): stycken av källans rader (en lång rad som avslutar en
  mening blir ett eget stycke, korta rader hålls ihop), långa textmassor delas vid meningsgränser, webb- och
  e-postadresser blir länkar, och ingressen döljs när beskrivningen är utfälld om beskrivningen börjar med den.
- **Fråga AI** (`chat.py`), kan döljas helt med `CHAT_ENABLED=false` (#69: menyvalet och `chat.js` tas bort ur
  `index.html`, sidan Om hoppar över AI-texterna, `/api/chat*` ger 404):
  1. `classify`: enkla sökfrågor besvaras direkt av `search_answer`, utan AI.
  2. `scope_check`: spärr före AI och webb. Frågan stoppas om den nämner ett namn med versal som inte finns bland
     appens evenemang, platser, arrangörer eller kommuner, eller om den inte rör evenemang. Webben söks bara när
     frågan nämner ett evenemang, en plats eller en arrangör i appen.
  3. Kön till Ollama (högst 2 samtidigt), sessioner per flik och sparade svar (`chat_cache.py`).
  4. Valfri SearXNG (`websearch.py`, `SEARXNG_URL`).
- **Åtkomst** (`access.py`): inga `/docs`, `/redoc` eller `/openapi.json`. `/api/health` och `/api/refresh` bara lokalt
  (`require_local`: loopback och privata adresser utan proxyhuvuden). Fråga AI: spärrarna gäller bara frågor som går
  till AI:n (`admit` i `chat_stream`, efter sparade svar och före webbsökning): 5 per 30 minuter och session och
  `chat_limiter`, 20 per 30 minuter och IP (`client_ip`: sista adressen i `X-Forwarded-For` bara när anropet kommer
  från en lokal adress).
  Gränssnittet får aldrig börja använda `/api/health` eller `/api/refresh`, eftersom de nekas utifrån.
- **Bilder via appen** (`images.py`, #60): `/api/events` ger `/img/<nyckel>` (hash av källans adress). Bara adresser
  som finns i evenemangen, bara publika värdar (även vid omdirigering), bara riktiga bilder (JPEG, PNG, GIF, WebP,
  AVIF, högst 10 MB, kontrolleras mot innehållet). Hämtas vid första visningen och sparas i `data/images/`, högst 4
  samtidigt. Sidan har `Content-Security-Policy: img-src 'self' data:` och `referrer` `no-referrer`, så webbläsaren
  kontaktar aldrig källorna. Nya källor med bilder behöver inget extra.
- **Städning** (`main.cleanup`, `events.purge_old`): körs efter varje hämtning från källorna (även `POST /api/refresh`)
  och vid start, aldrig oftare (användarens beslut). Rensar källdata från före morgonkörningen (05:00) och från
  avstängda källor, inaktuella AI-svar, bilder utan evenemang och `.tmp`-filer, utgångna samtal, IP-adresser i
  spärren och, efter morgonkörningen, alla chattsamtal. En källa som fallerar på morgonen får två nya försök (5 min)
  innan dess data tas bort. Ingen åtkomstlogg (`--no-access-log`), och Dockers logg roteras (3 × 10 MB).
  Ny lagrad data ska rensas där när den blir inaktuell, och läggas till i tabellen i `docs/data-och-integritet.md`.
- **Besöksstatistik** (#66, `visits.py`, `besoksinfo.py`, `geoip.py`): av som standard, på med `BESOKSINFO_PASSWORD`.
  `GET /` räknas (inte robotar, `HeadlessChrome` eller prefetch). Unika per dygn: sha256 av dygnets salt + IP +
  User-Agent. `data/besoksinfo.json`: `days` (dagens besökare med IP, plats, enhet, webbläsare, OS, hänvisning) och
  `daily` (summerat). `cleanup` summerar dygn som är slut (IP-adresserna och saltet tas bort) och rensar dagar äldre än
  13 månader. Sparas högst en gång i minuten och vid avslut. `/besoksinfo`: HTTP Basic (valfritt användarnamn),
  `login_limiter` 10 fel per 15 min och IP, `noindex`, `no-store`, egen CSP, ingen JavaScript. Plats: DB-IP City Lite
  (`data/geoip/dbip-city-lite.mmdb`, hämtas vid start och efter morgonkörningen om den saknas eller är äldre än 32
  dagar, cirka 60 MB), kräver länken till DB-IP på sidan. Kontrastkontrollen tar med sidan när `BESOKSINFO_PASSWORD`
  finns i miljön. Sidan Om beskriver statistiken när den är på (`visit_stats` i `/api/events`).
- **Lagring hos besökaren:** inga cookies. `localStorage` (`route`, `sidebar`) och `sessionStorage` (`chat-session`).
  Beskrivs i `docs/data-och-integritet.md` och på sidan Om (Cookies och lagring). Nya värden ska läggas till där.
- **Licens:** MIT (`LICENSE`). README har avsnitten Licens och ansvar (inga anspråk på källornas innehåll, inget
  ansvar för funktionen) och Framtagen med Claude Code. Samma avsnitt finns på sidan Om applikationen (källistan där
  byggs av appens källor). Nya källor ska läggas till i README (Funktioner) och i `docs/kallor.md`.
- **Dokumentation** (#61): README är kort och konkret (vad, skärmdumpar, kom igång, viktigaste inställningarna,
  länkar, licens, Claude Code). Detaljerna finns i `docs/` (`README.md` är innehållsförteckningen): `arkitektur.md`,
  `installation.md`, `funktioner.md`, `kallor.md`, `fraga-ai.md`, `data-och-integritet.md`, `api.md`,
  `utveckling.md`. Nytt innehåll läggs i rätt dokument i `docs/`, inte i README. Skärmdumparna i `docs/screenshots/` skapas med
  `tools/readme-screenshots.mjs` (lista, kalender, Fråga AI, Motorsport, mobil). Ta om dem när gränssnittet ändras
  synligt.
- **Arkitekturbild** (#63, #64), gjord som i användarens repo `tubalainen/reforger-server-manager`: källan
  `docs/arkitektur/varmlandsinfo.architecture.json` (Archify, `meta.animation: "trace"`, svenska texter i
  `meta.translations`, hänvisningar till koden), det interaktiva och animerade diagrammet `varmlandsinfo.html` och
  skärmbilden `varmlandsinfo.png`. README och `docs/arkitektur.md` visar bilden som länk till https://tubalainen.github.io/varmlandsinfo/arkitektur/varmlandsinfo.html
  (GitHub Pages från `main`, `/docs`, med `docs/.nojekyll`). Ta om den när delar, källor eller kopplingar ändras: läs
  Archifys `archify/SKILL.md`, uppdatera källan och `meta.repository.revision` (en pushad commit med de citerade
  raderna), kör `finalize` i en kopia i scratchpaden (så att kvittona inte hamnar i repot) med
  `ARCHIFY_CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, granska i båda lägena och ta skärmbilden i
  ljust läge med Playwright (1440 px bred, till och med korten, när animeringen lyser upp huvudvägen). Gränsen
  "Docker-container" (#65) är en Archify-boundary, som ritas som en rektangel runt sina delar: containerns sju delar
  ligger därför samlade i två kolumner i mitten, webbläsarens delar till vänster, externa tjänster och `/data` till
  höger och källorna (en nod) till vänster om Hämtning. Inget utanför containern får hamna innanför rektangeln.

## Beslut och önskemål från användaren (gäller framåt)

- Release bara när användaren ber om det. Rena dokumentationsändringar (t.ex. README) committas utan release.
- Fråga AI: bara frågor om evenemang som finns i appen. Allt annat stoppas **innan** AI eller webb anropas
  (exempel: Arvikamarten ok, Liseberg nej). Nya källor och kategorier ska också fungera i Fråga AI:
  `CATEGORY_WORDS`, `EVENT_WORDS`, `QUICK` och ord i spärren.
- Integritet: texterna i appen ska vara sanna om vart frågor skickas (lokal Ollama, och SearXNG när den är på).
- Ingen gammal data efter morgonkörningen.
- Närliggande källor ska visas som **en** källa i gränssnittet när användaren ber om det (Loppisar, Motorsport).
- Motorsport: både bil- (SBF) och MC-sport (Svemo), publika tävlingar och prova på-dagar, Värmland + Karlskoga.
- Användaren vill att efterforskning görs ordentligt och att frågor ställs när vägval är oklara.
- Fråga AI: högst 5 frågor till AI:n per 30 minuter och samtal och 20 per 30 minuter och IP-adress. Frågor som
  besvaras utan AI (sökfrågor, sparade svar, stoppade frågor) ska aldrig begränsas.
- All lagrad data ska rensas när den blir inaktuell, men bara i samband med hämtningarna från källorna (och vid
  start). Ingen återkommande städning utöver det.
- Bilderna visas via appen, så att källorna aldrig ser besökarna.
- Besöksstatistik: bara med lösenord (`BESOKSINFO_PASSWORD`, av som standard), inga cookies, unika per dygn. Fulla
  IP-adresser bara för innevarande dygn (rensas när dygnet är slut), summerad statistik i 13 månader. Plats via en
  lokal geodatabas, aldrig via en extern tjänst.
- Ingen proxykonfiguration eller nya inställningar för omvända proxyer i appen. Sådant hanterar användaren utanför
  appen. Lösningar ska fungera utan konfiguration både med och utan proxy.
- Kategorifiltren ska vara begripliga och stå i strikt bokstavsordning (inga egna filter först). Allmänna
  paraplykategorier som "Evenemang" ska inte visas som egna filter.

## Lärdomar i utvecklingsmiljön (Claudes molnmiljö)

- **Venv** för tester och körning finns ofta i scratchpaden (`<scratchpad>/venv`). Annars: `python -m venv` och
  `pip install -r requirements-dev.txt`.
- **Testa mot sparad data i stället för att hämta om:** kopiera en datakatalog och sätt `updated` i
  `<källa>.json` till nu för källor som inte ska hämtas. Då hämtas bara nya eller ändrade källor vid start.
- **Fejkade tjänster:** en liten FastAPI-fil räcker som fejk-Ollama (`/api/tags`, `/api/chat` som strömmar NDJSON)
  och fejk-SearXNG (`/search` med JSON).
- **Stoppa processer:** `pkill -f "[u]vicorn main:app"` i ett **eget** Bash-anrop. Står mönstret i samma
  kommandorad som något annat avslutas det egna skalet (exit 144). `pkill` träffar inte Python-skript som körs via
  heredoc (`python - <<EOF`), eftersom URL:en inte står på kommandoraden. Starta aldrig långa hämtningar i bakgrunden
  utan en säker stoppmekanism (`timeout`).
- **Webbläsarprov:** Playwright finns globalt: `NODE_PATH=$(npm root -g) node skript.mjs` (i ESM via
  `createRequire`). Kontrastkontrollen: `NODE_PATH=$(npm root -g) node tools/contrast-check.mjs`.
- **Skärmdumpar med riktiga bilder:** bilderna visas via appen, och appen hämtar dem genom miljöns proxy (httpx
  följer `HTTPS_PROXY`). Kör `NODE_PATH=$(npm root -g) node tools/readme-screenshots.mjs http://localhost:8080`.
  Kör om vid varningen "alla bilder laddades inte" och granska bilderna innan de checkas in.
- **CI-status** utan `gh`: `curl -s "https://api.github.com/repos/tubalainen/varmlandsinfo/actions/runs?head_sha=<sha>"`
  i en `until`-loop tills CI, Publicera Docker-image och Release är klara.
- **Bandy (analys 2026-09-29):** IF Boltic (tidigare BS BolticGöta) spelar Bandyallsvenskan 2026/27, inte Elitserien, och
  finns inte hos Visit Värmland. Bandyförbundets matcher finns i Profixio: API:t kräver nyckel (elitserien.se har en
  egen proxy för Elitserien), men de publika sidorna `profixio.com/app/lx/competition/leagueid<id>?t=schedule` är
  serverrenderade (Allsvenskan herr 2026/27: `leagueid28502`, hemmaplan Tingvalla Isstadion). Klubbens SportAdmin-sida
  `ifboltic.com/match/?ID=521641` listar också kommande matcher (även ungdom och träningsmatcher).
- Uvicorn läser `index.html` vid start: starta om servern efter ändringar i HTML eller Python.

