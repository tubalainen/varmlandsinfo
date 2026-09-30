# Säkerhet

Värmlandsinfo är byggd för att köras bakom en omvänd proxy med HTTPS, till exempel Nginx Proxy Manager. Appen ska
aldrig publiceras direkt mot internet. Här står hur appen skyddar sig, hur den bör driftas och vilka risker som finns
kvar. Hur data lagras och rensas står i [Data och integritet](data-och-integritet.md), och vem som får anropa vad i
[API](api.md#åtkomst-till-apit).

## Säkerhetsanalys (2026-09-30)

En säkerhetsgenomgång av koden, beroendena och driften gav åtta åtgärdspaket:

| Paket | Risk | Status |
|-------|------|--------|
| [#85](https://github.com/tubalainen/varmlandsinfo/issues/85) Uppgradera FastAPI/Starlette, lås beroendena (CVE-2025-62727, CVE-2026-48710) | Hög | Klart |
| [#86](https://github.com/tubalainen/varmlandsinfo/issues/86) Drift bakom Nginx Proxy Manager, "bara lokalt" bara via loopback | Medel | Klart |
| [#87](https://github.com/tubalainen/varmlandsinfo/issues/87) Inga interna detaljer (Ollamas adress, undantag, sökvägar) till besökarna | Medel | Klart |
| [#88](https://github.com/tubalainen/varmlandsinfo/issues/88) Säkerhetshuvuden och strikt CSP | Låg–medel | Planerat |
| [#89](https://github.com/tubalainen/varmlandsinfo/issues/89) Gränser för anropens storlek, besöksstatistiken och bildhämtningen | Medel | Planerat |
| [#90](https://github.com/tubalainen/varmlandsinfo/issues/90) Fråga AI länkar bara till underlaget, bildproxyn kontrollerar serverns adress | Låg–medel | Planerat |
| [#91](https://github.com/tubalainen/varmlandsinfo/issues/91) Härdad container och leveranskedja | Låg | Planerat |
| [#92](https://github.com/tubalainen/varmlandsinfo/issues/92) Råd för Ollama och SearXNG (CVE-2026-7482 m.fl.) | Hög om Ollama nås från nätet | Planerat |

## Rekommenderad drift med Nginx Proxy Manager

Nginx Proxy Manager (NPM) kör i en egen container på samma värd. Appen och NPM delar ett Docker-nät, och bara NPM
tar emot trafik från internet (port 80 och 443 i routern). Port 7799 öppnas aldrig i routern.

### 1. Porten bara på värden

Docker publicerar portar förbi värdens brandvägg (ufw och firewalld ser inte Dockers regler). Med standardvärdet
`7799` nås appen därför från hela nätet, okrypterat och förbi NPM. Bind porten till värden i `.env`:

```bash
VARMLANDSINFO_PORT=127.0.0.1:7799
```

Appen nås då bara från värden själv (<http://localhost:7799>), och från internet bara via NPM.

### 2. Gemensamt Docker-nät med NPM

En NPM-container kommer inte åt värdens `127.0.0.1`. Anslut i stället appen till NPM:s nät med en
`docker-compose.override.yaml` bredvid `docker-compose.yaml` (docker compose läser den automatiskt, och den checkas
inte in):

```yaml
services:
  varmlandsinfo:
    networks: [default, npm]

networks:
  npm:
    external: true
    name: npm_default        # NPM:s nät, se `docker network ls`
```

Kör `docker compose up -d`. I NPM pekar värden (*Proxy Host*) på `http`, `varmlandsinfo` och port `8080`.

### 3. Inställningar i NPM

- **SSL:** certifikat från Let's Encrypt, *Force SSL*, *HTTP/2 Support* och *HSTS Enabled*.
- **Details:** *Block Common Exploits* på. *Websockets Support* behövs inte. *Cache Assets* av (appen sätter själv
  rätt cachehuvuden).
- **Advanced:** begränsa kroppens storlek (NPM tillåter 2000 MB som standard) och stäng adresserna som bara är till
  för den som driftar appen:

  ```nginx
  client_max_body_size 64k;
  location ~ ^/api/(health|refresh) { return 404; }
  ```

- **Valfritt, takt för Fråga AI:** appen begränsar frågorna till AI:n, men inte sökfrågorna. Vill du begränsa alla
  frågor per IP-adress lägger du till en zon i NPM:s `data/nginx/custom/http_top.conf`:

  ```nginx
  limit_req_zone $binary_remote_addr zone=varmlandsinfo_chat:10m rate=30r/m;
  ```

  och i *Advanced* för värden:

  ```nginx
  location = /api/chat {
      limit_req zone=varmlandsinfo_chat burst=10 nodelay;
      include conf.d/include/proxy.conf;
  }
  ```

NPM lägger till `X-Forwarded-For` och `X-Real-IP`. Appen använder den sista adressen i `X-Forwarded-For` för
spärrarna per IP-adress och för besöksstatistiken. Ligger något framför NPM (t.ex. Cloudflare) behöver NPM ställas in
så att den ersätter adressen med besökarens (`real_ip_header`), annars räknas alla besökare som samma adress.

## Skydd i appen

- **Bara inifrån containern:** `/api/health` och `/api/refresh` svarar bara på loopback (127.0.0.1 och ::1) utan
  proxyhuvuden. Dockers healthcheck fungerar som vanligt, och en manuell uppdatering görs med `docker exec` (se
  [Installation](installation.md#kom-igång)). Anrop från det lokala nätverket, Dockers bryggnät eller via en proxy
  nekas, eftersom Docker kan få anrop från internet att se ut att komma från en privat adress (t.ex. via IPv6).
- **Spärrar per IP-adress** (Fråga AI och lösenordet till `/besoksinfo`) litar bara på `X-Forwarded-For` när anropet
  kommer från en privat adress, alltså från proxyn. Därför får port 7799 inte nås direkt från andra datorer: den som
  når porten från nätet kan ange vilken adress som helst.
- **Inga interna detaljer till besökarna:** fel hos Ollama visas med fasta texter, utan Ollamas adress (ofta en
  privat IP-adress), undantag eller Ollamas eget felsvar, och `/api/events` visar varken datakatalogen eller
  lagringsfelets detaljer. Allt finns i loggen, och i `/api/health` inifrån containern.
- **Beroenden:** alla beroenden är låsta till kända versioner i `app/constraints.txt`, se
  [Utveckling](utveckling.md#beroenden).
- **Ingen API-dokumentation**, ingen åtkomstlogg, inga cookies, appen körs som vanlig användare i containern, och
  bilderna visas via appen så att källorna aldrig ser besökarna.

## Lösenordet till besöksstatistiken

`/besoksinfo` skyddas med HTTP Basic och `BESOKSINFO_PASSWORD`. Använd ett långt slumpat lösenord (t.ex.
`openssl rand -base64 24`) och öppna sidan bara via HTTPS.
