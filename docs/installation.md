# Installation och inställningar

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

Första hämtningen tar ungefär 10–30 sekunder, eftersom Visit Värmlands API ger max 50 evenemang per sida.
Därefter sparas datan och laddas direkt vid omstart.

Evenemangen hämtas automatiskt en gång per dygn, från varje källa vid en egen slumpad tid mellan 08:00 och 13:00
(`REFRESH_WINDOW`). Vill du uppdatera direkt anropar du
`POST /api/refresh` från samma dator eller det lokala nätverket, till exempel
`curl -X POST http://localhost:7799/api/refresh` (se [API](api.md)).

### Köra en viss version

Sätt `VARMLANDSINFO_TAG` i `.env`, till exempel `VARMLANDSINFO_TAG=0.11.0`, och kör
`docker compose pull && docker compose up -d`. `latest` pekar alltid på senaste release.

Paketet på ghcr.io blir privat första gången det publiceras. Gör det publikt under
*GitHub → Packages → varmlandsinfo → Package settings → Change visibility*,
eller logga in med `docker login ghcr.io` innan du kör `docker compose pull`.

### Nå appen utifrån

Appen har ingen egen konfiguration för omvända proxyer (nginx, Traefik, Caddy, Nginx Proxy Manager, Cloudflare
Tunnel …). Sådant hanteras utanför appen, och om och hur appen nås utifrån bestämmer du. Anrop via en proxy räknas
aldrig som lokala, så `/api/health` och `/api/refresh` nekas automatiskt utifrån. Ska appen nås från internet
rekommenderas HTTPS via en omvänd proxy. Råd och en uppsättning med Nginx Proxy Manager finns i
[Säkerhet](sakerhet.md#råd-nå-appen-från-internet-via-nginx-proxy-manager).

## Inställningar

Alla inställningar görs i `.env`, som docker compose läser automatiskt. Utgå från `.env.example`.
`.env` checkas aldrig in i git, så privata adresser stannar lokalt.

| Variabel             | Standard           | Beskrivning |
|----------------------|--------------------|-------------|
| `VARMLANDSINFO_PORT` | `7799`             | Port på värdmaskinen. Standard är alla gränssnitt (0.0.0.0). `127.0.0.1:7799` gör att appen bara nås från värden själv (och via en omvänd proxy på värden, se [Säkerhet](sakerhet.md)). |
| `VARMLANDSINFO_TAG`  | `latest`           | Imagetagg från ghcr.io (`latest` eller en version, t.ex. `0.11.0`). |
| `TICKETMASTER_API_KEY` | *(tom)*          | API-nyckel för Ticketmaster. Tom betyder att källan är avstängd. |
| `TICKETMASTER_RADIUS_KM` | `150`          | Sökradie kring Värmland (km). |
| `SHL_TEAM_CODE`      | `FBK`              | Lag vars hemmamatcher hämtas från SHL. |
| `CHAT_ENABLED`       | `true`             | Visa Fråga AI. `false` döljer funktionen helt: menyvalet, sidan, texterna om AI-chatten på sidan Om och API:t för chatten (svarar 404). |
| `OLLAMA_URL`         | *(tom)*            | Adress till Ollama. Tom betyder att AI:n är avstängd och att Fråga AI bara svarar på sökfrågor. |
| `OLLAMA_MODEL`       | `llama3.1:8b`      | Modell i Ollama. |
| `OLLAMA_NUM_CTX`     | `16384`            | Kontextfönster (tokens) för modellen. |
| `CHAT_MAX_EVENTS`    | `40`               | Max antal evenemang som skickas med till modellen per fråga. |
| `SEARXNG_URL`        | *(tom)*            | Adress till SearXNG för AI:ns webbsökning. Tom betyder att webbsökningen är avstängd. |
| `SEARXNG_RESULTS`    | `5`                | Max antal webbträffar per fråga (1–20). |
| `SEARXNG_LANGUAGE`   | `sv`               | Språk för webbsökningen. |
| `BESOKSINFO_PASSWORD` | *(tom)*           | Lösenord till besöksstatistiken på `/besoksinfo`. Tom betyder att statistiken är avstängd och inga besök räknas. |
| `REFRESH_WINDOW`     | `08:00-13:00`      | Tidsfönstret för den dagliga hämtningen. Varje källa hämtas vid en slumpad tid i fönstret, ny varje dag (minst 31 minuter, så att nya försök ryms). Ersätter `DAILY_REFRESH_TIME` och `REFRESH_MINUTES`, som inte längre används. |
| `VARMLANDSINFO_DATA` | `./data`           | Katalog på värden där hämtad data sparas. |
| `PUID` / `PGID`      | `1000` / `1000`    | Användare och grupp som äger filerna i datakatalogen. |
| `TZ`                 | `Europe/Stockholm` | Tidszon, avgör bland annat vad som räknas som "idag". |

## AI-chatten med Ollama

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
   Sätt `OLLAMA_HOST=0.0.0.0` i Ollamas miljö. Ollama har ingen inloggning: använd minst version 0.17.1 och låt
   brandväggen släppa in bara appens värd på port 11434 (se [Säkerhet](sakerhet.md#råd-ollama-och-searxng)).
4. Starta om: `docker compose up -d`. Sidan *Fråga AI* visar vilken modell som används och
   varnar om Ollama inte går att nå eller om modellen saknas.

Hur chatten fungerar beskrivs i [Fråga AI](fraga-ai.md).

## Webbsökning via SearXNG (valfritt)

AI:n kan komplettera svaren med information från webben via en egen [SearXNG](https://docs.searxng.org/)-instans.

1. Kör SearXNG, till exempel med [searxng-docker](https://github.com/searxng/searxng-docker).
2. Slå på JSON-svar i SearXNG:s `settings.yml` och starta om SearXNG:
   ```yaml
   search:
     formats:
       - html
       - json
   ```
   Har du SearXNG:s `limiter` påslagen kan den stoppa appens anrop. Stäng av den eller släpp igenom appens adress.
3. Ange adressen i `.env`, till exempel `SEARXNG_URL=http://<ip-adress>:8888` (eller `http://searxng:8080` om
   SearXNG körs i samma compose-projekt), och starta om: `docker compose up -d`. Publicera inte SearXNG mot
   internet (se [Säkerhet](sakerhet.md#råd-ollama-och-searxng)).

När webben används beskrivs i [Fråga AI](fraga-ai.md#webbsökning).

## Besöksstatistik (valfritt)

1. Sätt ett lösenord i `.env`, till exempel `BESOKSINFO_PASSWORD=ett-långt-lösenord`, och starta om:
   `docker compose up -d`.
2. Öppna `http://<värd>:7799/besoksinfo`. Webbläsaren frågar efter lösenordet (användarnamnet spelar ingen roll).
3. Nås appen utifrån ska det ske med HTTPS, till exempel via din omvända proxy, så att lösenordet inte skickas i klartext.

Första gången hämtar appen DB-IP:s fria geodatabas (cirka 60 MB, uppackad cirka 130 MB i `data/geoip/`) för att visa
land och ort. Den uppdateras en gång i månaden. Vad som räknas och sparas står i
[Data och integritet](data-och-integritet.md#besöksstatistik).
