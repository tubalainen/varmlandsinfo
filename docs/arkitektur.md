# Arkitektur

[![Arkitekturöversikt](arkitektur/varmlandsinfo.png)](https://tubalainen.github.io/varmlandsinfo/arkitektur/varmlandsinfo.html)

Klicka på bilden för den [interaktiva, animerade översikten](https://tubalainen.github.io/varmlandsinfo/arkitektur/varmlandsinfo.html), eller ändra
[Archify-specifikationen](arkitektur/varmlandsinfo.architecture.json).

Översikten är skapad med [Archify](https://github.com/tt-a1i/archify) utifrån koden, och varje del hänvisar till
källkoden. Den streckade rutan visar gränsen för Docker-containern: allt innanför körs i containern, medan
webbläsaren, `/data` (en volym på värden), källorna, bildservrarna, Ollama och SearXNG ligger utanför. I den interaktiva versionen följer en animering huvudvägen genom appen (*Rörelse*/*Stilla*), och du kan
klicka på delarna för att se hänvisningarna, följa vägar mellan dem (PATH), jämföra typer (LENS), byta tema och
exportera bilden.

## Delarna

| Del | Vad den gör | Kod |
|-----|-------------|-----|
| Webbgränssnitt | Lista, kalender, Fråga AI och Om applikationen. Hämtar allt från appen. | `app/static/` |
| FastAPI-app | Sidan, API:t och bilderna på port 8080 i en Docker-container. | `app/main.py` |
| Åtkomst | `/api/health` och `/api/refresh` bara lokalt, spärren per IP i Fråga AI. | `app/access.py` |
| Fråga AI | Direktsökning, avgränsning, spärrar, kö till Ollama och valfri webbsökning. | `app/chat.py`, `app/websearch.py` |
| Bildproxy | Hämtar evenemangens bilder från källorna vid första visningen och sparar dem. | `app/images.py` |
| Evenemang i minnet | Källornas evenemang sammanslagna och kategoriserade. | `app/events.py`, `app/merge.py`, `app/categories.py` |
| Schemaläggare | Hämtar varje källa en gång om dagen vid en slumpad tid mellan 08:00 och 13:00, gör nya försök och städar bort inaktuell data. | `app/main.py`, `app/timetable.py` |
| Hämtning | En modul per källa. API-källor som JSON, övriga som webbsidor (HTML). | `app/events.py`, `app/sources/` |
| Källorna | Visit Värmland, Ticketmaster och SHL (API) samt Profixio (bandy och handboll), CCC, Scalateatern, Great Event, loppisarna, SBF, Svemo, Säffle och Kil (webbsidor). | se [Källor](kallor.md) |
| `/data` | Volym på värden: källdata, sparade AI-svar och bilder. | se [Data och integritet](data-och-integritet.md) |
| Ollama, SearXNG | Egna tjänster utanför appen. Båda är valfria. | se [Installation](installation.md) |

## Uppdatera bilden

Diagrammets källa är [`arkitektur/varmlandsinfo.architecture.json`](arkitektur/varmlandsinfo.architecture.json).
Ändras arkitekturen uppdateras källan (delar, kopplingar och hänvisningar till koden, med radnummer och
`meta.repository.revision` satt till en commit som innehåller raderna), och sedan körs Archify:

```bash
# Archify: https://github.com/tt-a1i/archify (katalogen archify/ i repot)
node <archify>/bin/archify.mjs finalize architecture docs/arkitektur/varmlandsinfo.architecture.json \
  docs/arkitektur/varmlandsinfo.html --repo-root . --quality showcase
```

`finalize` validerar diagrammet mot koden och kontrollerar det i en webbläsare (sätt `ARCHIFY_CHROME` till Chrome
eller Chromium om den inte hittas). `varmlandsinfo.png` är en skärmbild av det interaktiva diagrammet i ljust läge
(1440 px bred, till och med korten). Archifys kvitton (`*.delivery.json`, `*.finalize*.json`, `*.browser-check.json`)
checkas inte in.

Det interaktiva diagrammet publiceras med GitHub Pages från katalogen `docs/` på `main` (`docs/.nojekyll` gör att
filerna visas som de är): <https://tubalainen.github.io/varmlandsinfo/arkitektur/varmlandsinfo.html>.
