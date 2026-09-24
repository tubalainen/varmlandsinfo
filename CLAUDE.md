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
4. **Merga när det är grönt.** När CI (`ci.yml`) och Docker-bygget (`docker-publish.yml`) är gröna på
   PR:en mergas den till `main` (merge commit). En merge publicerar ingen image och skapar ingen release.
5. **Release bara på användarens kommando.** En release kan innehålla en eller flera mergade PR:er.
   - **Versionen räknas fram automatiskt** (om användaren inte anger en) enligt semver utifrån
     `[Unreleased]` i CHANGELOG: nya funktioner eller ändrat beteende ger MINOR (0.0.1 → 0.1.0), bara
     buggfixar ger PATCH (0.1.0 → 0.1.1) och brytande ändringar efter 1.0 ger MAJOR.
   - Skapa en release-issue och en release-PR som sätter versionen i `app/version.py` och flyttar
     `[Unreleased]` i `CHANGELOG.md` till `## [X.Y.Z] - ÅÅÅÅ-MM-DD`. Uppdatera jämförelselänkarna
     längst ner och lista de ingående PR:erna i PR-beskrivningen.
   - Merga release-PR:en när den är grön. `release.yml` ser att versionen på `main` saknar release och
     skapar taggen `vX.Y.Z`, GitHub-releasen (CHANGELOG-avsnittet plus genererade notes) och imagen
     `ghcr.io/tubalainen/varmlandsinfo:X.Y.Z` / `X.Y` / `latest`.
   - Vänta in flödet **Release** (båda jobben) och rapportera länken till releasen.
   - Obs: taggar kan inte pushas från Claudes molnmiljö, och manuell körning av flöden nekas. Release
     via merge till `main` är därför vägen. Höj aldrig versionen i vanliga PR:er.
6. **Ingen `edge`.** Images publiceras bara vid release.
7. **Städa efter varje release.** När releasen är klar och flödet **Release** är grönt:
   - inga öppna PR:er ska ligga kvar. Mergade PR:er är stängda, och överblivna eller ersatta PR:er
     stängs med en kort kommentar om varför
   - alla issues som ingår i releasen är stängda (`completed`), och övriga inaktuella issues stängs med
     motivering (`not_planned`)
   - mergade grenar tas bort. Arbetsgrenen återskapas från `main` vid nästa ändring
   - inga väntande påminnelser eller PR-bevakningar ligger kvar för releasens PR:er
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
