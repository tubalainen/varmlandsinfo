# Värmlandsinfo – instruktioner för Claude

Dockerbaserad webbapp (FastAPI + statisk HTML/JS) som visar evenemang i Värmland från Visit Värmlands API,
med AI-chatt via Ollama. Användaren kommunicerar på svenska: skriv issues, PR:er, commits och svar på svenska.

## Arbetsflöde (ska alltid följas)

1. **Issue först.** Varje förändring kopplas till en GitHub-issue. Finns ingen, formulera en med
   bakgrund, krav och acceptanskriterier innan arbetet börjar. Issuen är baslinjen för förändringen.
2. **Pull request.** Arbeta i en gren och öppna en PR mot `main`. PR-beskrivningen följer
   `.github/pull_request_template.md` och stänger issues med `Closes #N`. En PR kan omfatta flera issues.
   Varje commit refererar sin issue, t.ex. `(#7)`.
3. **CHANGELOG.** Lägg till en rad per ändring under `## [Unreleased]` i `CHANGELOG.md`, med issue-nummer.
4. **Grönt före merge.** CI (`ci.yml`) och Docker-bygget (`docker-publish.yml`) ska vara gröna.
   Merga bara när användaren ber om det.
5. **Release när användaren ber om det.** En release kan innehålla en eller flera mergade PR:er:
   - Välj nästa version enligt semver (`app/version.py`). Under 0.x: ny funktion höjer MINOR, fix höjer PATCH.
   - Skapa en release-PR som sätter versionen i `app/version.py` och flyttar `[Unreleased]` i
     `CHANGELOG.md` till `## [X.Y.Z] - ÅÅÅÅ-MM-DD`, uppdaterar jämförelselänkarna längst ner och listar
     de ingående PR:erna.
   - Merga release-PR:en. `release.yml` ser att versionen på `main` saknar release och skapar då
     taggen `vX.Y.Z`, GitHub-releasen (CHANGELOG-avsnittet plus genererade notes) och imagen
     `ghcr.io/tubalainen/varmlandsinfo:X.Y.Z` / `X.Y` / `latest`.
   - Kontrollera att flödet Release gick igenom och länka releasen för användaren.
   - Obs: taggar kan inte pushas från Claudes molnmiljö, och manuell körning av flöden nekas. Det
     automatiska flödet vid push till `main` är därför vägen till en release.

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
