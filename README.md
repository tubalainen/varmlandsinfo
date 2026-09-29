<p align="center"><img src="app/static/icons/icon.svg" alt="Värmlandsinfo" width="120"></p>

# Värmlandsinfo

En webbapp i Docker som samlar **aktuella evenemang i Värmland** från flera källor på ett ställe: som lista, i en
kalender och via **Fråga AI**, en chatt som svarar med hjälp av din egen Ollama. Öppen källkod under
[MIT-licensen](LICENSE).

![Evenemangslistan med filter, kategorier i bokstavsordning och källornas status](docs/screenshots/lista.jpg)

| Kalendern (mörkt läge) | Fråga AI | Mobil (mörkt läge) |
|------------------------|----------|--------------------|
| ![Kalendern med en vecka per rad och evenemangen färgkodade per typ](docs/screenshots/kalender.jpg) | ![Fråga AI besvarar en sökfråga direkt med en lista i datumordning](docs/screenshots/fraga-ai.jpg) | <img src="docs/screenshots/mobil.jpg" alt="Evenemangslistan på mobil i mörkt läge" width="200"> |

## Arkitektur

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/arkitektur/varmlandsinfo-mork.svg">
  <img src="docs/arkitektur/varmlandsinfo-ljus.svg" alt="Arkitekturen i Värmlandsinfo: webbläsaren, FastAPI-appen och dess delar, lagringen i /data, källorna samt Ollama och SearXNG">
</picture>

Skapad med [Archify](https://github.com/tt-a1i/archify) utifrån koden. Se [Arkitektur](docs/arkitektur.md).

## Funktioner

- **Evenemang från tio källor**, sammanslagna så att samma evenemang visas en gång: Visit Värmland, Ticketmaster,
  Karlstad CCC, Scalateatern, SHL, Great Event, Loppisar (Karlstad Loppis och loppisar.com) och Motorsport (SBF och
  Svemo).
- **Lista och kalender** dag för dag, med filter på kategori, kommun, källa och datum.
- **Fråga AI:** sökfrågor besvaras direkt, och frågor som kräver en bedömning besvaras av din egen Ollama.
  Valfri webbsökning via SearXNG.
- **Integritet:** inga cookies eller spårning, bilderna visas via appen, AI:n körs lokalt och inaktuell data
  rensas bort.
- **Ljust och mörkt läge**, fungerar på mobil.

## Kom igång

Kräver Docker med Compose-pluginet.

```bash
git clone https://github.com/tubalainen/varmlandsinfo.git
cd varmlandsinfo
cp .env.example .env      # justera inställningarna, t.ex. OLLAMA_URL
docker compose pull
docker compose up -d
```

Öppna <http://localhost:7799>. Evenemangen hämtas första gången vid start och sedan varje morgon kl. 05.00.

De viktigaste inställningarna i `.env`:

| Variabel | Beskrivning |
|----------|-------------|
| `OLLAMA_URL` | Adress till din Ollama, t.ex. `http://host.docker.internal:11434`. Tom = Fråga AI svarar bara på sökfrågor. |
| `SEARXNG_URL` | Adress till SearXNG för webbsökning i Fråga AI. Tom = av. |
| `TICKETMASTER_API_KEY` | API-nyckel för Ticketmaster. Tom = källan är av. |
| `VARMLANDSINFO_PORT` | Port på värden (standard `7799`). |

Alla inställningar och hur Ollama och SearXNG sätts upp står i [Installation](docs/installation.md).

## Dokumentation

| | |
|---|---|
| [Arkitektur](docs/arkitektur.md) | Delarna i appen och hur de hänger ihop |
| [Installation och inställningar](docs/installation.md) | Docker, versioner, `.env`, Ollama, SearXNG |
| [Funktioner](docs/funktioner.md) | Lista, kalender, filter, kategorier |
| [Källor](docs/kallor.md) | Källorna och hur ofta de anropas |
| [Fråga AI](docs/fraga-ai.md) | Direktsökning, AI, avgränsning, spärrar, webbsökning |
| [Data och integritet](docs/data-och-integritet.md) | Lagring, städning, bilder via appen, cookies |
| [API](docs/api.md) | Adresserna och vem som får anropa dem |
| [Utveckling](docs/utveckling.md) | Projektstruktur, tester, releaser |

Ändringar per version: [CHANGELOG.md](CHANGELOG.md). Arbetsflöde: [CONTRIBUTING.md](CONTRIBUTING.md).

## Licens och ansvar

- **Licens:** öppen källkod under [MIT-licensen](LICENSE). Du får använda, kopiera, ändra och dela koden fritt, så
  länge licenstexten följer med.
- **Källornas innehåll:** appen gör inga anspråk på innehållet från källorna. Texter, bilder och uppgifter om
  evenemangen tillhör respektive källa och upphovsperson. Appen visar ett urval och länkar till källan för varje
  evenemang. Kontrollera alltid tider och andra uppgifter hos arrangören eller källan.
- **Inget ansvar:** appen levereras i befintligt skick, utan garantier av något slag. Inget som helst ansvar tas för
  appens funktion, för att uppgifterna stämmer eller är aktuella, för AI-chattens svar eller för följderna av att
  använda appen.

## Framtagen med Claude Code

Värmlandsinfo är framtagen med hjälp av [Claude Code](https://claude.com/claude-code), Anthropics AI-assistent för
programmering. Idéer, krav och beslut kommer från projektets ägare. Claude Code har skrivit det mesta av koden,
testerna och dokumentationen. Arbetssättet finns i [CLAUDE.md](CLAUDE.md).

Claude används bara för att utveckla appen. Fråga AI använder din egen Ollama, och inga frågor skickas till Claude
eller någon annan AI-tjänst i molnet.
