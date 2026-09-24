# Värmlandsinfo

En liten webbapp i Docker som visar en översikt över **aktuella evenemang i Värmland**, i datumordning.

Första datakällan är Visit Värmlands öppna API:
<https://turid.visitvarmland.com/api/v8/events>

## Funktioner

- Alla kommande och pågående evenemang, grupperade per dag (Idag, Imorgon …).
- Evenemangstyp (kategori) med ikon, färg och en kort beskrivning av typen.
- Sammanfattning, längre beskrivning, plats (med kartlänk) och arrangör.
- Länk till evenemanget på visitvarmland.com, samt biljett- och webbplatslänk när sådana finns.
- Bilder från evenemanget (klicka för att förstora).
- Filter: fritextsök, kategori, kommun och datumintervall, samt "Visa varje tillfälle"
  för evenemang som återkommer flera gånger.
- Datan hämtas automatiskt på nytt varje timme (styrs av `REFRESH_MINUTES`).

## Kom igång

Kräver Docker med Compose-pluginet.

```bash
# Använd den färdiga imagen från GitHub Container Registry
docker compose pull
docker compose up -d

# …eller bygg lokalt
docker compose up -d --build
```

Öppna sedan <http://localhost:8080>.

Första hämtningen tar ungefär 10–30 sekunder, eftersom API:et ger max 50 evenemang per sida.

### Inställningar (`docker-compose.yaml`)

| Variabel          | Standard           | Beskrivning                                    |
|-------------------|--------------------|------------------------------------------------|
| `REFRESH_MINUTES` | `60`               | Hur ofta evenemangen hämtas på nytt (minuter). |
| `TZ`              | `Europe/Stockholm` | Tidszon som avgör vad som räknas som "idag".   |

Byt porten genom att ändra `"8080:8080"`, till exempel till `"8123:8080"`.

## API

- `GET /api/events`: alla aktuella evenemang i JSON, sorterade på nästa tillfälle.
- `GET /api/health`: status, antal evenemang och tidpunkt för senaste uppdatering.

## Publicering till ghcr.io

GitHub Actions-flödet `.github/workflows/docker-publish.yml` bygger imagen för
`linux/amd64` och `linux/arm64` och publicerar den till
`ghcr.io/tubalainen/varmlandsinfo`:

- `latest` vid push till standardgrenen
- en tagg per gren och `sha-<commit>` vid varje push
- `1.2.3` och `1.2` när du pushar en tagg som `v1.2.3`
- vid pull requests byggs imagen bara, utan att publiceras

Paketet blir privat första gången det publiceras. Gör det publikt under
*GitHub → Packages → varmlandsinfo → Package settings → Change visibility*,
eller logga in med `docker login ghcr.io` innan du kör `docker compose pull`.

## Projektstruktur

```
app/
  main.py          FastAPI-server, hämtning och normalisering av evenemang
  categories.py    Klassificering och beskrivning av evenemangstyper
  static/          Webbgränssnittet (HTML/CSS/JS)
Dockerfile
docker-compose.yaml
```
