# Värmlandsinfo – instruktioner för Claude

Dockerbaserad webbapp (FastAPI + statisk HTML/JS) som visar evenemang i Värmland från Visit Värmlands API,
med AI-chatt via Ollama. Användaren kommunicerar på svenska: skriv issues, PR:er, commits och svar på svenska.

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
  CCC, Scalateatern, Great Event, Karlstad Loppis och loppisar.com är vanliga webbplatser). Hämta inte oftare än nödvändigt, varken i appen
  eller under utveckling.
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
  servern, bara i minnet, så appen ska köras som en process)
- `app/main.py`: FastAPI-rutter och schemaläggning
- `app/static/`: gränssnittet. `app.js` sköter navigering (`#/lista`, `#/kalender`, `#/fraga`, `#/om`), filter
  och lista, `calendar.js` kalendern, `chat.js` Fråga AI, `about.js` Om applikationen och `icons.js`
  SVG-ikonerna. Nya funktioner ska beskrivas på sidan Om applikationen (`about.js`)
