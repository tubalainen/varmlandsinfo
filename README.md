# Värmlandsinfo

En liten webbapp i Docker som visar en översikt över **aktuella evenemang i Värmland** i datumordning,
med en **AI-chatt** (via Ollama) där du kan ställa frågor om evenemangen.

Första datakällan är Visit Värmlands öppna API:
<https://turid.visitvarmland.com/api/v8/events>

## Funktioner

- **Evenemangslista:** alla kommande och pågående evenemang, grupperade per dag (Idag, Imorgon …).
- **Evenemangstyp:** kategori med ikon, färg och en kort beskrivning av typen.
- **Detaljer:** sammanfattning, längre beskrivning, plats (med kartlänk) och arrangör.
- **Länkar:** till evenemanget på visitvarmland.com, samt biljett- och webbplatslänk när sådana finns.
- **Bilder:** från evenemanget (klicka för att förstora).
- **Filter:** fritextsök, kategori, kommun och datumintervall, samt "Visa varje tillfälle"
  för evenemang som återkommer flera gånger.
- **AI-chatt:** knappen *Fråga AI* öppnar en chatt kopplad till din egen Ollama. Ställ frågor som
  "Vad händer i Karlstad i helgen?" eller "Finns det barnaktiviteter nästa vecka?". Svaren strömmas,
  länkar till evenemangen och visar vilket underlag de bygger på. Följdfrågor som "och på söndag då?"
  fungerar också.
- **Uppdatering:** knappen *Uppdatera evenemang* hämtar allt på nytt direkt. Dessutom körs en
  automatisk uppdatering varje dag (standard 05:00).
- **Lagring:** allt som hämtas sparas i `./data` på värden. Vid omstart visas evenemangen direkt,
  utan att API:et anropas i onödan.

## Kom igång

Kräver Docker med Compose-pluginet.

```bash
git clone https://github.com/tubalainen/varmlandsinfo.git
cd varmlandsinfo
cp .env.example .env      # justera inställningarna, t.ex. OLLAMA_URL
docker compose pull       # hämtar imagen från ghcr.io
docker compose up -d
```

Öppna sedan <http://localhost:7799>.

Vill du bygga imagen själv i stället: `docker compose up -d --build`.

Första hämtningen tar ungefär 10–30 sekunder, eftersom API:et ger max 50 evenemang per sida.
Därefter sparas datan och laddas direkt vid omstart.

### Köra en viss version

Sätt `VARMLANDSINFO_TAG` i `.env`, till exempel `VARMLANDSINFO_TAG=0.0.1`, och kör
`docker compose pull && docker compose up -d`. `latest` pekar på senaste release och `edge` på senaste
bygget från `main`.

## Inställningar

Alla inställningar görs i `.env`, som docker compose läser automatiskt. Utgå från `.env.example`.
`.env` checkas aldrig in i git, så privata adresser stannar lokalt.

| Variabel             | Standard           | Beskrivning |
|----------------------|--------------------|-------------|
| `VARMLANDSINFO_PORT` | `7799`             | Port på värdmaskinen. |
| `VARMLANDSINFO_TAG`  | `latest`           | Imagetagg från ghcr.io (`latest`, `edge` eller en version). |
| `OLLAMA_URL`         | *(tom)*            | Adress till Ollama. Tom betyder att AI-chatten är avstängd. |
| `OLLAMA_MODEL`       | `llama3.1:8b`      | Modell i Ollama. |
| `OLLAMA_NUM_CTX`     | `16384`            | Kontextfönster (tokens) för modellen. |
| `CHAT_MAX_EVENTS`    | `40`               | Max antal evenemang som skickas med till modellen per fråga. |
| `DAILY_REFRESH_TIME` | `05:00`            | Tidpunkt för den dagliga uppdateringen. |
| `REFRESH_MINUTES`    | `0`                | Extra uppdatering var N:e minut (0 = av). |
| `VARMLANDSINFO_DATA` | `./data`           | Katalog på värden där hämtad data sparas. |
| `PUID` / `PGID`      | `1000` / `1000`    | Användare och grupp som äger filerna i datakatalogen. |
| `TZ`                 | `Europe/Stockholm` | Tidszon, avgör bland annat vad som räknas som "idag". |

## Lagring av data

Allt som hämtas från Visit Värmlands API sparas på värden i katalogen `./data` bredvid
`docker-compose.yaml`. Katalogen monteras som volym till `/data` i containern och skapas automatiskt.

| Fil                        | Innehåll |
|----------------------------|----------|
| `data/visitvarmland.json`  | Rådata från API:et (alla evenemang och kommuner) samt tidpunkt för hämtningen. |

- **Vid start** läses filen in och evenemangen visas direkt. API:et anropas bara om datan är äldre än
  den senaste schemalagda uppdateringen, till exempel om containern varit avstängd över natten.
- **Vid uppdatering** skrivs filen atomärt (först till en temporär fil som sedan byter namn), så att
  en krasch inte lämnar en trasig fil.
- **Om en hämtning misslyckas** behålls senast sparade data.
- Eftersom rådata sparas kan en ny version av appen tolka om den utan att hämta allt på nytt.
- Filerna ägs av användaren `PUID`/`PGID` (standard 1000). Kör `id` på värden för att se dina värden
  och sätt dem i `.env`.
- Vill du lägga datan någon annanstans sätter du `VARMLANDSINFO_DATA`, till exempel `/srv/varmlandsinfo`.
- Radera `data/visitvarmland.json` för att tvinga fram en helt ny hämtning vid nästa start.

## AI-chatt med Ollama

1. Installera [Ollama](https://ollama.com) och hämta en modell, till exempel:
   ```bash
   ollama pull llama3.1:8b
   ```
   Modeller som är bra på svenska ger bättre svar, till exempel `qwen2.5:7b`, `gemma3:12b` eller `llama3.1:8b`.
2. Ange adressen i `.env`:
   - Ollama på samma maskin som Docker: `OLLAMA_URL=http://host.docker.internal:11434`
   - Ollama på en annan dator i nätverket: `OLLAMA_URL=http://<ip-adress>:11434`

   Basadressen räcker, men en fullständig endpoint som `http://<ip-adress>:11434/v1/chat/completions`
   fungerar också.
3. Om Ollama körs på en annan dator måste den lyssna på nätverket och inte bara på `localhost`.
   Sätt `OLLAMA_HOST=0.0.0.0` i Ollamas miljö.
4. Starta om: `docker compose up -d`. Knappen *Fråga AI* visar vilken modell som används och
   varnar om Ollama inte går att nå eller om modellen saknas.

**Så fungerar det:** appen skickar inte alla evenemang till modellen. För varje fråga tolkar den
tidsuttryck (idag, i helgen, nästa vecka, 3 oktober, i oktober …), kommuner, evenemangstyper och
sökord. Utifrån det väljer den ut de mest relevanta evenemangen (högst `CHAT_MAX_EVENTS`) och
skickar dem som underlag. Modellen instrueras att bara svara utifrån underlaget.

## API

| Metod | Sökväg             | Beskrivning |
|-------|--------------------|-------------|
| GET   | `/api/events`      | Alla aktuella evenemang i JSON, sorterade på nästa tillfälle. |
| GET   | `/api/health`      | Version, antal evenemang, senaste och nästa uppdatering, lagringsstatus. |
| POST  | `/api/refresh`     | Hämtar alla evenemang på nytt och svarar när det är klart. |
| GET   | `/api/chat/status` | Om AI-chatten är konfigurerad och om Ollama går att nå. |
| POST  | `/api/chat`        | Chatt: `{"messages": [{"role": "user", "content": "…"}]}`. Svaret strömmas som NDJSON. |

## Versioner och releaser

Projektet använder semantisk versionering. Versionen står i `app/version.py` och visas i sidfoten.
Ändringar listas i [CHANGELOG.md](CHANGELOG.md).

En tagg `vX.Y.Z` skapar automatiskt en GitHub-release och publicerar imagen
`ghcr.io/tubalainen/varmlandsinfo:X.Y.Z` (samt `X.Y` och `latest`) för `linux/amd64` och `linux/arm64`.
Hela arbetsflödet med issues, pull requests och releaser beskrivs i [CONTRIBUTING.md](CONTRIBUTING.md).

Paketet på ghcr.io blir privat första gången det publiceras. Gör det publikt under
*GitHub → Packages → varmlandsinfo → Package settings → Change visibility*,
eller logga in med `docker login ghcr.io` innan du kör `docker compose pull`.

## Projektstruktur

```
app/
  main.py          FastAPI-server, API och schemaläggning
  events.py        Hämtning och normalisering av evenemang från Visit Värmland
  chat.py          AI-chatt: urval av evenemang och anrop till Ollama
  categories.py    Klassificering och beskrivning av evenemangstyper
  version.py       Versionsnummer
  static/          Webbgränssnittet (HTML/CSS/JS)
tests/             Tester (pytest)
.github/workflows/ CI, Docker-publicering och releaser
Dockerfile
docker-entrypoint.sh  Ger /data rätt ägare och startar appen som PUID:PGID
docker-compose.yaml
.env.example
data/                 Sparad data (skapas vid körning, ingår inte i git)
```
