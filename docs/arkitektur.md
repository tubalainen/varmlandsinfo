# Arkitektur

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="arkitektur/varmlandsinfo-mork.svg">
  <img src="arkitektur/varmlandsinfo-ljus.svg" alt="Arkitekturen i Värmlandsinfo: besökarens webbläsare, FastAPI-appen med åtkomst, Fråga AI, bildproxy, evenemang i minnet, schemaläggare och hämtning, lagringen i /data, källorna och de valfria tjänsterna Ollama och SearXNG">
</picture>

Bilden är skapad med [Archify](https://github.com/tt-a1i/archify) utifrån koden. Varje del i diagrammet hänvisar till
källkoden. Öppna [det interaktiva diagrammet](arkitektur/varmlandsinfo.html) (ladda ner filen och öppna den i en
webbläsare) för att se hänvisningarna, följa vägar mellan delarna och byta tema.

## Delarna

| Del | Vad den gör | Kod |
|-----|-------------|-----|
| Webbgränssnitt | Lista, kalender, Fråga AI och Om applikationen. Hämtar allt från appen. | `app/static/` |
| FastAPI-app | Sidan, API:t och bilderna på port 8080 i en Docker-container. | `app/main.py` |
| Åtkomst | `/api/health` och `/api/refresh` bara lokalt, spärren per IP i Fråga AI. | `app/access.py` |
| Fråga AI | Direktsökning, avgränsning, spärrar, kö till Ollama och valfri webbsökning. | `app/chat.py`, `app/websearch.py` |
| Bildproxy | Hämtar evenemangens bilder från källorna vid första visningen och sparar dem. | `app/images.py` |
| Evenemang i minnet | Källornas evenemang sammanslagna och kategoriserade. | `app/events.py`, `app/merge.py`, `app/categories.py` |
| Schemaläggare | Hämtar varje morgon (05:00), gör nya försök och städar bort inaktuell data. | `app/main.py` |
| Hämtning | En modul per källa. API-källor som JSON, övriga som webbsidor (HTML). | `app/events.py`, `app/sources/` |
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
eller Chromium om den inte hittas). SVG-filerna exporteras från det interaktiva diagrammet med *Exportera → SVG · Light*
och *SVG · Dark* och sparas som `varmlandsinfo-ljus.svg` och `varmlandsinfo-mork.svg`. Archifys kvitton
(`*.delivery.json`, `*.finalize*.json`, `*.browser-check.json`) checkas inte in.
