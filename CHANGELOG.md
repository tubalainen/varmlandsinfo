# Changelog

Alla viktiga ändringar i projektet dokumenteras här.
Formatet följer [Keep a Changelog](https://keepachangelog.com/sv/1.1.0/) och projektet använder
[semantisk versionering](https://semver.org/lang/sv/).

## [Unreleased]

### Tillagt
- Hämtad data sparas utanför containern i `./data` (volym `/data`). Vid omstart laddas den direkt
  och API:et anropas bara när datan är inaktuell (#7)
- `PUID`/`PGID` styr vem som äger filerna i datakatalogen (#7)
- Kalendervy med en vecka per rad och veckonummer. Klick på en dag visar dagens evenemang, och
  samma filter som i listan gäller (#8)

- Skydd för Visit Värmlands API: knappen hämtar högst var 5:e minut, `REFRESH_MINUTES` är minst 30,
  takten anpassas efter API:ets kvot, kommunlistan hämtas en gång per vecka och ett misslyckat
  försök görs om efter 30 minuter (#9)

### Ändrat
- Containern startar som root bara för att ge `/data` rätt ägare och kör sedan appen som
  `PUID:PGID` (tidigare en fast användare med uid 10001) (#7)

### Rättat
- `REFRESH_MINUTES=0` gav en evig hämtloop i den första versionen. Nu betyder 0 alltid "av" (#9)

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
