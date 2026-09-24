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
- **Checka aldrig in privata adresser** (t.ex. användarens Ollama-IP) eller `.env`.
- Var snäll mot Visit Värmlands API (60 anrop/minut, cirka 15 anrop per full hämtning).
  Hämta inte oftare än nödvändigt, varken i appen eller under utveckling.

## Struktur

- `app/events.py`: hämtning, normalisering och lagring (`/data/visitvarmland.json`)
- `app/chat.py`: urval av evenemang och Ollama-anrop
- `app/main.py`: FastAPI-rutter och schemaläggning
- `app/static/`: gränssnittet (`app.js` lista, `calendar.js` kalender, `chat.js` chatt)
