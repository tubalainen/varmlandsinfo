# Changelog

Alla viktiga ändringar i projektet dokumenteras här.
Formatet följer [Keep a Changelog](https://keepachangelog.com/sv/1.1.0/) och projektet använder
[semantisk versionering](https://semver.org/lang/sv/).

## [Unreleased]

## [0.0.1] - 2026-09-24

Första releasen.

### Tillagt
- Översikt över aktuella evenemang i Värmland från Visit Värmlands API, i datumordning med
  kategori och beskrivning av typen, bilder, länkar och filter (#1)
- AI-chatt kopplad till Ollama för frågor om evenemangen, med strömmade svar,
  följdfrågor och länkar till underlaget (#2)
- Knappen "Uppdatera evenemang" och daglig schemalagd uppdatering (`DAILY_REFRESH_TIME`) (#3)
- Versionsnummer i gränssnittet och i `/api/health`, CHANGELOG, CI och ett releaseflöde som
  skapar en GitHub-release och publicerar imagen på ghcr.io (#4)
- `.env.example` med alla inställningar

### Ändrat
- Standardport på värden är nu 7799 (#5)

[Unreleased]: https://github.com/tubalainen/varmlandsinfo/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/tubalainen/varmlandsinfo/releases/tag/v0.0.1
