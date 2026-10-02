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
   - inga öppna PR:er eller kvarglömda grenar (utöver `main`) ska finnas. Grenar kan inte tas bort från molnmiljön
     (se Lärdomar), så kontrollera att de redan finns i `main` och be användaren ta bort dem
   - alla issues som ingår i releasen är stängda (`completed`), och övriga inaktuella issues stängs
     med motivering (`not_planned`)
   - inga väntande påminnelser eller bevakningar ligger kvar
   - rapportera kort vad som städats

## Utveckling

- Tester: `pip install -r requirements-dev.txt && python -m pytest -q tests`. Beroendena är låsta i
  `app/constraints.txt` (se `docs/utveckling.md#beroenden` för hur den uppdateras)
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
  CCC, Scalateatern, Great Event, Karlstad Loppis, loppisar.com, SBF:s LoTS, Svemo TA, Profixio, Säffle, Kil och
  Skoghalls Folkets Hus är vanliga
  webbplatser).
  Profixio (bandy och handboll): varje sida är cirka 0,5 MB. Gå igenom serierna bara en gång i veckan (`DISCOVER_DAYS`), och hämta
  sedan bara serierna med lag från Värmland.
  Svemo TA har 13 000+ historiska tävlingar: bläddra aldrig igenom hela listan, bara sista sidorna bakåt.
  Hämta inte oftare än nödvändigt, varken i appen eller under utveckling. Testa mot sparad data (se Lärdomar).
- **Var VÄLDIGT snäll mot källorna** (användarens beslut, #76): källorna uppdateras sällan, så hellre vänta till nästa
  hämtning än riskera att bli spärrad. Högst ett nytt försök per anrop (429 och 5xx, aldrig tidigare än
  `Retry-After`, aldrig om källan ber om mer än 60 s), 401/403 pausar källan till nästa morgonkörning, och nya
  försök görs bara vid morgonkörningen (2 st, 15 min emellan). Lägg aldrig till tätare försök.
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

## Återuppta arbetet (senast uppdaterat 2026-10-02, efter v0.32.1)

Läs detta först i en ny session. Senaste releasen är **v0.32.1**. Allt är pushat till `main`, CI och Docker-bygget är
gröna och det finns inga andra grenar eller öppna PR:er.

- **Säkerhetsanalysen är klar** (2026-09-30, v0.30.0–v0.30.3, `docs/sakerhet.md` med status per paket). Åtta
  åtgärdspaket, ett issue per paket. Användarens prioritet: webbservern och det besökarna når via
  hemsidan ska inte vara en säkerhetsrisk, utan att appen låses ned i onödan. Klara: #85 (FastAPI 0.142.2/Starlette
  1.7.0, låsta beroenden i `app/constraints.txt`), #86 och #93 (råd för drift bakom Nginx Proxy Manager, appen litar
  på localhost och LAN), #87 (inga interna detaljer till besökarna), #89 (gränser: `main.BodyLimit` 32 KB,
  `visits.MAX_VISITORS_PER_DAY` och `MAX_PER_DIMENSION`, bildproxyns takt `images.DOWNLOAD_BURST`), #88
  (`main.SECURITY_HEADERS` på alla svar och strikt `main.PAGE_CSP` för sidan: gränssnittet får aldrig använda
  inbäddade skript, `style`-attribut i HTML, `eval` eller externa resurser. `style.cssText` från JS går bra), #90 (bara länkar i
  `chat.allowed_links` blir klickbara i AI-svar, `sources` har `links`, svar med andra adresser sparas inte;
  `images.peer_is_public`), #91 (härdad container, `apt-get upgrade`, `security.yml`, `SECURITY.md`) och #92 (råd för
  Ollama och SearXNG i `docs/sakerhet.md`). Användaren kör Nginx Proxy Manager i en egen container på samma värd.
- **Tidigare arbete:** snabbvalen i Fråga AI borttagna (#77, v0.27.0), källorna Säffle och Kil som gruppen
  Kommunerna (#79, v0.28.0), bara kommuner i filtret Kommun (#81, v0.28.1), arkitekturbilden med 13 källor och
  aktuella kodhänvisningar (#80, v0.28.2), källan Handboll och arkitekturbilden med 14 källor (#82, v0.29.0) och
  skärmdumparna med Handboll (#83).
- **Inte släppt:** inget. v0.32.1 innehåller skärmdumparna med v0.32.0 (#99). v0.32.0 innehåller den nya källan Riksteatern med arkitekturbilden med 16 källor (#98,
  Fråga AI känner igen källornas namn) och skärmdumparna med v0.31.0 (#97). v0.31.0 innehåller den nya källan Skoghalls Folkets Hus och `merge.same_slot` (#96),
  Visit Värmlands kommun ur platsen först och `merge.duplicate_listing` (#95) och arkitekturbilden med 15 källor.
  v0.30.3 innehåller arkitekturbilden och skärmdumparna efter säkerhetsarbetet (#94). v0.30.1 innehåller #91 (härdad container i `docker-compose.yaml`, `apt-get upgrade` i
  `Dockerfile`, flödet `security.yml` med pip-audit och Trivy varje måndag, `SECURITY.md`) och v0.30.2 råden för
  Ollama och SearXNG (#92). Blir *Säkerhetskontroll* röd: rätta beroendet eller föreslå användaren en PATCH-release
  (ett nytt bygge får Debians rättningar).
- **Öppet:** inga issues. Säkerhetsanalysens alla paket (#85–#93) är klara.
- **Möjliga nästa steg** (se Analys av källor som saknas nedan): Tickster (kräver en nyckel som användaren i så fall
  registrerar). Fråga användaren innan det påbörjas.
- **Känd begränsning:** namnfrågor i Fråga AI ("Vad händer på Medis?") matchar titlar före platser, så evenemang på
  "Medis stora scen" utan Medis i titeln kommer inte med. Gäller alla platser och fanns före #79.

## Läget (v0.29.0, 2026-09-29)

- **Källor** (`app/sources/`, prioritetsordning): Visit Värmland (API), Ticketmaster (API, kräver nyckel, av som
  standard), Karlstad CCC, Scalateatern, SHL (Färjestads hemmamatcher), Bandy (Profixio, #72), Handboll (Profixio,
  #82), Great Event, Karlstad Loppis + loppisar.com
  (grupp **Loppisar**), SBF/LoTS + Svemo TA (grupp **Motorsport**, `sources/motorsport.py`), Säffle + Kil (grupp
  **Kommunerna**, `sources/kommunerna.py`, #79), Skoghalls Folkets Hus (`sources/skoghall.py`, #96), Riksteatern
  (`sources/riksteatern.py`, #98). En källas
  `group` gör att
  flera källor visas som en i gränssnittet (menyn, filtret Källa, korten, sidan Om), medan hämtning, lagring och status
  i `/api/health` är per källa.
- **Motorsport:** publika tävlingar och prova på-dagar i Värmland + Karlskoga. Läget avgörs av banans namn (`PLACES`
  i `motorsport.py`) och i andra hand arrangörens ort. Nya banor och byar läggs till i `PLACES` (rallyn har ofta
"Tillfällig" som bana och utgår från en by), men kontrollera först mot sparad SBF-data att ordet inte träffar banor
utanför området. motorsportivarmland.nu undersöktes som rallykälla (#51) men är en nyhetssajt utan strukturerad
kalender, och SBF har redan rallyna. LoTS och Svemo är ASP.NET/Telerik:
  sidbyte med postback (`__VIEWSTATE` + `__EVENTTARGET` från knappen med title "Next/Previous/Last Page").
- **Kommunerna** (#79): Säffle och Kil använder Sitevision med Soleil IT:s moduler. Säffle: JSON från modulens
  appresource-anrop (`SAFFLE_ITEMS` och `SAFFLE_PATHS` ur sidans konfiguration), datum utan år (räknas fram, adressen
  ger året när den stämmer). Kil: `registerInitialState` i sidan, 25 per sida (`?start=25`), utan plats och kategori
  (`KIL_RULES` och `CHILD_RE` ur titeln). Samma titel (och plats) blir ett evenemang med flera tillfällen. Karlstad,
  Hammarö, Sunne (Sagolika Sunne) och Grums visar Visit Värmlands data.
- **Skoghalls Folkets Hus** (#96): WordPress med tillägget Theater. REST-API:t `wp-json/wp/v2/wp_theatre_prod`
  (produktionerna) och `categories`, sedan produktionssidan bara för de som inte är film (`is_live`: levande kategori
  eller titelprefix, och inget som säger "på bio", Seniorbio, Knattebio eller "livesänds till biografer"; användaren
  vill inte ha film eller sändningar på bioduken). Datum och tid ur biljettlänken (`tomovie@salongnr=N&tid=…&datum=…`,
  salong 6 = restaurangen), reserv i tabellraden. Andra platser (`PLACES`): Tingvallakyrkan (Karlstad) och Bygdegården
  Svenshult (Hammarö). Det mesta finns också hos Visit Värmland och slås ihop (`merge.same_slot`).
- **Riksteatern** (#98): öppet JSON-API, ett anrop: `riksteatern.se/api/performance/filter/all?region=17`
  (Värmlands län, filtren i `/api/performance/filteritems/all`). Bort: `isPrivate` (skolföreställningar, matiné för
  kommunen), `isCanceled`, `isPostponed` och bio. Sist i prioritetsordningen, det mesta slås ihop med Visit Värmland
  och Skoghall. Undersökningen av Folkets Hus (2026-10-01): de små husen (Årjäng, Högboda, Oleby …) har inga egna
  evenemangslistor, hyrs mest ut, och det som spelas där finns hos Visit Värmland eller Riksteatern. varmland.bio
  är bara bio (användaren vill inte ha bio i nya källor, befintliga källors filmvisningar får vara kvar).
- **Analys av källor som saknas** (2026-09-29): möjligt nästa steg är Tickster (Event Dump API, en fil per dygn,
  kräver nyckel). Handboll är gjord (#82). Avfärdade: Svenska kyrkan
  (användarens beslut), Wermland Opera (captcha), trav (Färjestadstravet förbjuder kopiering), svenskfotboll.se
  (Cloudflare), stats.innebandy.se (robots.txt spärrar AI-agenter), Nöjesfabriken (redan täckt av Visit Värmland),
  Storfors (fritext) och Karlstads universitet (mest för studenter). 2026-10-01 (#98): Folkets Hus med egna sajter
  (Årjäng, Högboda, Oleby) saknar evenemangslistor, Karlskoga kommuns kalender länkar bara till Visit Värmland,
  varmland.bio (bara bio), danskalendern.se (skräpblogg), ABF Värmland och bygdegardarna.se (inga listor).
- **Kommuner** (`kommuner.py`, #81): filtret Kommun har bara `KOMMUNER` (Värmlands 16 + Karlskoga och Degerfors, som
  Visit Värmlands kommunlista). `common.finalize` sätter kommunen med `kommun()` ur källans kommun, platsens adress
  och namn: kommunnamn, orter (`ORTER`, t.ex. Väse → Karlstad) och postnummerprefix som bara används i en kommun
  (`POSTNUMMER`). Annars ingen kommun. Nya orter läggs till i `ORTER` (inte korta eller tvetydiga namn). Fråga AI
  förstår orterna (`find_municipalities`, `_index`). Motorsportens banor och byar (`motorsport.PLACES`) är kvar där.
- **Kategorier** (`categories.py`, regler i `common.finalize`): `SOURCE_NAMES` byter källornas namn (Visit Värmlands
  *Evenemang* och *Övriga evenemang* blir *Övrigt*, *Motor* blir *Motorträffar*). `split_loppis` bryter ut *Loppis* ur
  marknadskategorin, och `split_motorsport` ger tävlingar *Motorsport*, medan *Motorträffar* bara gäller träffar och
  fordonsutställningar. Sist lägger `refine` till kategorier ur ordregler (`KEYWORD_RULES`: Musik, Film, Spel och quiz,
  Träffar och caféer, Böcker och litteratur) från titeln, och från ingressen bara när källan saknar egen typ. Reglerna
  gäller inte loppisar och motorsport. *Övrigt* blir kvar bara när inget annat passar (Gratis räknas inte).
  Kategorifiltren står i bokstavsordning. Nya ordregler: pröva först mot sparad data så att de inte träffar fel.
  *SHL* (#68) sätts av källan SHL, *Bandy* (#70) av ordregeln (bara ordet bandy, inte innebandy eller bandyplanen).
  *Handboll* (#82) av källan Handboll och ordregeln, som bara gäller titeln (`TITLE_ONLY`: klubbens namn står ofta i
  ingressen, t.ex. "Karlskoga Handboll ordnar tipspromenad").
  **Bandy och innebandy är olika sporter** (bandy på is med skridskor) och får aldrig blandas ihop: varken i
  kategorier, sökrutan (`matches` i `app.js`) eller Fråga AI (#71). Kategorier i `categories.SOURCE_ONLY` följer med vid sammanslagning (`merge._absorb`),
  eftersom Visit Värmland och Ticketmaster har högre prioritet och annars skulle ta bort dem.
- **Ordning i listan och kalendern** (`multiDay` i `app.js`): under varje dag står evenemang som bara äger rum en dag
  före dem med flera datum (utställningar och återkommande evenemang lagras oftast som ett tillfälle per dag, inte
  som ett tillfälle över flera dagar), sedan tid och titel.
- **Sammanslagning** (`merge.py`): samma dag (varje dag i perioder ≤ 7 dagar), samma kommun och liknande titlar, eller
  `same_race` för motorsport med olika titlar. "loppis" och "konsert" m.fl. räknas inte som gemensamma ord. Inom samma
  källa bara `duplicate_listing` (samma dag, starttid och plats, #95): Visit Värmland har ibland en post från
  arrangören och en från lokalen. Visit Värmlands kommun: platsens adress och namn först, sedan arrangören (#95).
  Mellan källor dessutom `same_slot` (#96): samma dag och starttid, ett gemensamt ord i lokalens namn (utom
  `PLACE_STOP`) och ett gemensamt ord i titeln eller den andras ingress. Mot sparad data slog den bara ihop riktiga
  dubbletter (Skoghall och Nötknäpparen på CCC).
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
  4. Följdfrågor (#73): `Session.previous_sources` (evenemangen som de 2 senaste svaren länkade) blir `pinned`
     först i AI:ns urval. `refers_back` (den, dit, efter det, "matchen" utan egen kommun/datum …, men inte "finns det"
     eller "den här veckan") gör en sökfråga i ett samtal till en AI-fråga. Utan Ollama visas förra svarets
     evenemang (`FOLLOWUP_NOTE`). `chatView.leave()` i `chat.js` (anropas av `navigate`) och Nytt samtal avbryter
     pågående fråga och tar bort samtalet på servern.
  5. Valfri SearXNG (`websearch.py`, `SEARXNG_URL`).
- **Åtkomst** (`access.py`): inga `/docs`, `/redoc` eller `/openapi.json`. `/api/health` och `/api/refresh` bara lokalt
  (`require_local`: loopback och privata adresser utan proxyhuvuden. Appen litar på LAN, användarens beslut i #93).
  Fel hos
  Ollama och lagringsfel visas för besökarna bara som fasta texter (`chat.AI_FAILED`, `chat.UNREACHABLE`,
  `main.STORAGE_ERROR`), detaljerna i loggen och `status(detail=True)` i `/api/health` (#87). Fråga AI: spärrarna gäller bara frågor som går
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
  spärren och, efter morgonkörningen, alla chattsamtal. En källa som fallerar på morgonen får två nya försök (15 min)
  innan dess data tas bort. Inga nya försök under resten av dygnet (#76). Ingen åtkomstlogg (`--no-access-log`), och Dockers logg roteras (3 × 10 MB).
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
  `CATEGORY_WORDS`, `EVENT_WORDS` och ord i spärren.
- Fråga AI har inga snabbval (borttagna i #77). Förslagskorten (`SUGGESTIONS`) finns kvar.
- Integritet: texterna i appen ska vara sanna om vart frågor skickas (lokal Ollama, och SearXNG när den är på).
- Ingen gammal data efter morgonkörningen.
- Närliggande källor ska visas som **en** källa i gränssnittet när användaren ber om det (Loppisar, Motorsport).
- Motorsport: både bil- (SBF) och MC-sport (Svemo), publika tävlingar och prova på-dagar, Värmland + Karlskoga.
- Användaren vill att efterforskning görs ordentligt och att frågor ställs när vägval är oklara.
- Fråga AI har sammanhang i samtalet för följdfrågor. Det rensas bara när man trycker Nytt samtal eller lämnar sidan
  Fråga AI (omladdning av sidan behåller det).
- Fråga AI: högst 5 frågor till AI:n per 30 minuter och samtal och 20 per 30 minuter och IP-adress. Frågor som
  besvaras utan AI (sökfrågor, sparade svar, stoppade frågor) ska aldrig begränsas.
- All lagrad data ska rensas när den blir inaktuell, men bara i samband med hämtningarna från källorna (och vid
  start). Ingen återkommande städning utöver det.
- Bilderna visas via appen, så att källorna aldrig ser besökarna.
- Besöksstatistik: bara med lösenord (`BESOKSINFO_PASSWORD`, av som standard), inga cookies, unika per dygn. Fulla
  IP-adresser bara för innevarande dygn (rensas när dygnet är slut), summerad statistik i 13 månader. Plats via en
  lokal geodatabas, aldrig via en extern tjänst.
- **Lås inte ned appen i onödan** (användarens beslut, #93): appen litar på localhost och LAN och ska fungera både
  med och utan omvänd proxy. Om och hur appen exponeras mot internet bestämmer den som driftar den. Proxyn är ett
  råd i `docs/sakerhet.md`, aldrig ett krav. Håll säkerhetsåtgärderna enkla och konkreta. Användaren kör själv Nginx
  Proxy Manager i en egen container på samma värd.
- Säkerhetsfynd kopplas till CVE/CWE, och beroenden hålls låsta (`app/constraints.txt`) och uppdaterade.
- Ingen proxykonfiguration eller nya inställningar för omvända proxyer i appen. Sådant hanterar användaren utanför
  appen. Lösningar ska fungera utan konfiguration både med och utan proxy.
- **Belasta inte Visit Värmland under utvecklingen** (användarens önskan 2026-09-29): inga omhämtningar, och inga
  kontrastkontroller eller skärmdumpar som laddar många bilder i onödan (Visit Värmlands bildserver svarade 429).
  Testa mot sparad data. Skärmdumpar och arkitekturbild tas om när användaren ber om det.
- Filtret Kommun har bara kommuner (Värmlands 16 + Karlskoga och Degerfors), inga orter (#81).
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
- **Utan att belasta källorna** (#82, #83): efter morgonkörningen (05:00) räknas gårdagens data som gammal, och appen
  hämtar då alla källor vid start. Kopiera i stället den sparade datakatalogen (med `images/`) och sätt `updated` till
  nu. Loggen ska säga "Sparad data är aktuell, ingen hämtning vid start". För kontrastkontrollen, som laddar många
  bilder, startas appen med en trasig proxy (`HTTPS_PROXY=http://127.0.0.1:9`, samma för `HTTP_PROXY` och gemener), så
  att inga bilder hämtas från källorna. Visit Värmlands bildserver svarade 429 även dagen efter.
- **CI-status** utan `gh`: `curl -s "https://api.github.com/repos/tubalainen/varmlandsinfo/actions/runs?head_sha=<sha>"`
  i en `until`-loop tills CI, Publicera Docker-image och Release är klara.
- **Grenar kan inte tas bort från molnmiljön** (#78): `git push origin --delete` bryter anslutningen ("remote end hung
  up") och GitHub-verktygen saknar borttagning av grenar. Kontrollera att grenen redan finns i `main`
  (`git merge-base --is-ancestor <sha> origin/main`) och be användaren ta bort den under *Branches* på GitHub.
- **Sessionsgrenen** (`claude/…`) ska inte pushas, eftersom den då blir en kvarglömd gren. Arbeta på `main` lokalt
  (`git checkout -B main origin/main`), så varnar inte stoppkontrollen för opushade commits.
- **Bandy** (`sources/bandy.py`, #72): Profixio (Laravel Livewire). API:t kräver nyckel, så de publika sidorna läses:
  tävlingslistan `/lx/SBF?t=competitions` (säsongens serier, id byts varje säsong), seriens spelschema
  `/lx/competition/leagueid<id>?t=schedule` (25 kommande matcher plus lagen) och nästa sida med ett Livewire-anrop
  (`__lazyLoad` på komponenten `infinite-scroll-next-page`, med sidans `csrf-token` och cookies). Lagsidor visar bara
  15 matcher och de gamla `/fx/`-sidorna ligger bakom Cloudflare. Avspark från `registerMatch(... kickoff: <unix>)`.
  **Språket** väljs efter besökaren: från Sverige svenska ("Omgång 1", "16 okt • 19:00"), via molnmiljöns proxy
  engelska ("Runde 1", "Oct 16 • 19:00"). Källan begär `Accept-Language: sv` och tolkningen klarar båda (#74).
  Testa alltid tolkningen mot svenska sidor.
  Läget: `PLACES` i `bandy.py` (arenor och klubbar) och motorsportens orter och kommuner. Seniorer och
  träningsmatcher, inte ungdom (`YOUTH_RE`: U17, F15, flick …, men "Katrineholm Bandy U" är ett utvecklingslag).
  2026/27: IF Boltic (Bandyallsvenskan herr, Tingvalla) och Slottsbron IF (träningsmatcher Mellansverige).
- **Handboll** (`sources/handboll.py`, #82): samma Profixio som bandyn (gemensam tolkning i `sources/profixio.py`),
  förbundet `lx/SHF`. Värmland hör till Handbollförbundet Väst. Seniorserier: `SENIOR_RE` (nationella serier, Svenska
  cupen och Dam/Herr 2–4 Väst). Serierna har oftast bara ett värmländskt lag (t.ex. IFK Hammarö av 23 i Herr 3 Väst),
  så lagens sidor läses i stället för seriernas: lagsidan `/lx/competition/leagueid<serie>/teams/<lag>` och
  Livewire-komponenten `lx.team.schedule` (`matchFilter: upcoming`, 15 matcher). En gång i veckan tävlingslistan och
  första sidan av varje seniorserie (alla lag står där) för att hitta lagen: ort i lagnamnet (`kommuner.kommun`) eller
  `CLUBS` (Hellton → Karlstad, Brukspôjkera → Forshaga). Matchens kommun: arenan, annars hemmalaget. "U" i lagnamnet är
  ett utvecklingslag (seniorer). Klubbar i Värmland: Arvika HK, Forshaga HK, HK Brukspôjkera, HK Grums, IF Hellton,
  IFK Hammarö, IFK Kristinehamn, Karlskoga HK, Kils AIKs HF, Skåre HK och Torsby IF. 2026/27 har bara Hellton, Hammarö
  och Kristinehamn seniorlag i serierna.
- **Docker går att köra i molnmiljön** (#91): starta daemonen med `(timeout 1800 dockerd > <scratchpad>/dockerd.log 2>&1 &)`.
  `docker pull` fungerar genom proxyn (Docker Hub kan svara 429, använd då ghcr.io, t.ex.
  `ghcr.io/aquasecurity/trivy`). Containrar når inte internet, så appen i en container belastar aldrig källorna.
  Bygga imagen: kopiera `Dockerfile`, `docker-entrypoint.sh`, `app/` och `/root/.ccr/ca-bundle.crt` (som `ca.crt`)
  till scratchpaden, lägg `COPY ca.crt /ca.crt` och `ENV PIP_CERT=/ca.crt SSL_CERT_FILE=/ca.crt` efter `FROM` i
  kopian och kör `docker build --network host` med `--build-arg` för `HTTP_PROXY`/`HTTPS_PROXY` (och gemener).
  Trivy: `docker run --network host` med proxyvariablerna, `SSL_CERT_FILE=/ca.crt` och docker-socketen.
- **Skoghalls Folkets Hus** svarar långsamt (en hämtning tar cirka 60 s), och via molnmiljöns proxy bryts
  förbindelsen ibland efter cirka 12 s (`ws_closed_mid_exchange`). Försök igen med `curl --retry 3 --retry-delay 10
  --retry-all-errors`, en förfrågan i taget.
- Uvicorn läser `index.html` vid start: starta om servern efter ändringar i HTML eller Python.
- **Archify** finns inte installerat: `git clone --depth 1 https://github.com/tt-a1i/archify` till scratchpaden och kör
  `archify/bin/archify.mjs`. I kopian av repot måste `origin` vara `https://github.com/tubalainen/varmlandsinfo`
  (`git remote set-url origin …`), annars stoppar Archify med `repository-evidence/origin-mismatch`, som `finalize`
  bara visar som "Renderer failed before emitting a structured diagnostic" (kör `render … --repo-root .` för felet).
- **Behörighetskontrollen för Bash** i molnmiljön svarar ibland inte ("no verdict") flera gånger i rad. Pausa och
  berätta för användaren i stället för att försöka många gånger (efter 10 i rad avbryts turen).

