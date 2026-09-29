# Utveckling

Arbetsflödet (issues, commits, releaser) beskrivs i [CONTRIBUTING.md](../CONTRIBUTING.md).

## Projektstruktur

```
app/
  main.py          FastAPI-server, API, schemaläggning och städning
  events.py        Hämtning, lagring och status för alla källor
  sources/         En modul per källa (visitvarmland, ticketmaster, ccc, scala, shl, greatevent, karlstadloppis, loppisar,
                   motorsport: SBF och Svemo)
  merge.py         Sammanslagning av samma evenemang från flera källor
  categories.py    Klassificering och beskrivning av evenemangstyper
  common.py        Gemensamma hjälpfunktioner (HTTP med rate limit, textrensning)
  images.py        Evenemangens bilder via appen
  chat.py          Fråga AI: urval av evenemang, kö och anrop till Ollama
  chat_cache.py    Sparade AI-svar
  sessions.py      Samtal (sessioner) i Fråga AI
  websearch.py     Webbsökning via SearXNG för Fråga AI
  access.py        Åtkomst till API:t: bara lokalt och spärren per IP i Fråga AI
  version.py       Versionsnummer
  static/          Webbgränssnittet (HTML/CSS/JS)
  static/icons/    Appens ikon (SVG och PNG i flera storlekar)
tests/             Tester (pytest)
tools/             Kontrastkontroll i ljust och mörkt läge, och skärmdumparna till dokumentationen
docs/              Dokumentationen
docs/arkitektur/   Arkitekturbilden: Archify-källan, det interaktiva diagrammet och SVG-bilderna
docs/screenshots/  Skärmdumparna i README och docs/
.github/workflows/ CI, Docker-publicering och releaser
Dockerfile
docker-entrypoint.sh  Ger /data rätt ägare och startar appen som PUID:PGID
docker-compose.yaml
.env.example
LICENSE               MIT-licensen
data/                 Sparad data (skapas vid körning, ingår inte i git)
```

## Köra lokalt och testa

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q tests
cd app && DATA_DIR=/tmp/data uvicorn main:app --port 8080
```

Kontrastkontrollen och skärmdumparna beskrivs i [CONTRIBUTING.md](../CONTRIBUTING.md).

## Versioner och releaser

Projektet använder semantisk versionering. Versionen står i `app/version.py`. Den visas i menyn
(som länk till releasen på GitHub), i `/api/health` och överst i loggen när containern startar:

```
$ docker logs varmlandsinfo
... INFO ============================================================
... INFO   Värmlandsinfo v0.11.0
... INFO   Release: https://github.com/tubalainen/varmlandsinfo/releases/tag/v0.11.0
... INFO   Källkod: https://github.com/tubalainen/varmlandsinfo
```

Ändringar listas i [CHANGELOG.md](../CHANGELOG.md), och releaserna finns under
[Releases](https://github.com/tubalainen/varmlandsinfo/releases).

- Ändringar committas direkt på `main`, kopplade till issues. Ingen image publiceras då.
- En release görs på begäran och kan innehålla flera ändringar. Då skapas en GitHub-release och
  imagen `ghcr.io/tubalainen/varmlandsinfo:X.Y.Z` (samt `X.Y` och `latest`) för `linux/amd64` och `linux/arm64`.
