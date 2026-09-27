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
  `docker-compose.yaml` och README.
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
- `app/main.py`: FastAPI-rutter och schemaläggning
- `app/static/`: gränssnittet. `app.js` sköter navigering (`#/lista`, `#/kalender`, `#/fraga`, `#/om`), filter
  och lista, `calendar.js` kalendern, `chat.js` Fråga AI, `about.js` Om applikationen och `icons.js`
  SVG-ikonerna. Nya funktioner ska beskrivas på sidan Om applikationen (`about.js`)

## Läget (v0.18.0, 2026-09-27)

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
- **Kategorier** (`categories.py`, regler i `common.finalize`): `split_loppis` bryter ut *Loppis* ur Visit Värmlands
  marknadskategori (som heter "Marknad, mässa och auktion"), och `split_motorsport` ger tävlingar *Motorsport*, medan
  *Motor* bara gäller motorträffar och fordonsutställningar. Egna filter står först: Gratis, Loppis, Motorsport.
- **Sammanslagning** (`merge.py`): samma dag (varje dag i perioder ≤ 7 dagar), samma kommun och liknande titlar, eller
  `same_race` för motorsport med olika titlar. "loppis" och "konsert" m.fl. räknas inte som gemensamma ord.
- **Fråga AI** (`chat.py`):
  1. `classify`: enkla sökfrågor besvaras direkt av `search_answer`, utan AI.
  2. `scope_check`: spärr före AI och webb. Frågan stoppas om den nämner ett namn med versal som inte finns bland
     appens evenemang, platser, arrangörer eller kommuner, eller om den inte rör evenemang. Webben söks bara när
     frågan nämner ett evenemang, en plats eller en arrangör i appen.
  3. Kön till Ollama (högst 2 samtidigt), sessioner per flik och sparade svar (`chat_cache.py`).
  4. Valfri SearXNG (`websearch.py`, `SEARXNG_URL`).
- **Städning** (`events.purge_old`, `main.cleanup`): efter morgonkörningen (05:00) och vid start tas data från före
  morgonkörningen bort, liksom avstängda källors filer, inaktuella AI-svar och gårdagens chattsamtal. En källa som
  fallerar på morgonen får två nya försök (5 min) innan dess data tas bort.
- **Dokumentation:** README har skärmdumpar i `docs/screenshots/` som skapas med `tools/readme-screenshots.mjs`
  (lista, kalender, Fråga AI, Motorsport, mobil). Ta om dem när gränssnittet ändras synligt.

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
- **Skärmdumpar med riktiga bilder:** externa bilder nås bara via miljöns proxy, och Playwright skickar då även
  localhost genom proxyn. Kör appen med `--host 0.0.0.0` och
  `SCREENSHOT_PROXY=$HTTPS_PROXY node tools/readme-screenshots.mjs http://$(hostname -I | awk '{print $1}'):8080`.
  Kör om vid varningen "alla bilder laddades inte" och granska bilderna innan de checkas in.
- **CI-status** utan `gh`: `curl -s "https://api.github.com/repos/tubalainen/varmlandsinfo/actions/runs?head_sha=<sha>"`
  i en `until`-loop tills CI, Publicera Docker-image och Release är klara.
- Uvicorn läser `index.html` vid start: starta om servern efter ändringar i HTML eller Python.

