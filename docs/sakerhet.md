# Säkerhet

Appen litar på localhost och det lokala nätverket (LAN). Hur den görs tillgänglig utanför nätverket bestämmer den
som driftar den. Appen fungerar både med och utan omvänd proxy. Här står hur appen skyddar sig, råd för den som vill
nå appen från internet och vilka risker som finns kvar. Hur data lagras och rensas står i [Data och integritet](data-och-integritet.md), och vem som får anropa vad i
[API](api.md#åtkomst-till-apit).

## Säkerhetsanalys (2026-09-30)

En säkerhetsgenomgång av koden, beroendena och driften gav åtta åtgärdspaket:

| Paket | Risk | Status |
|-------|------|--------|
| [#85](https://github.com/tubalainen/varmlandsinfo/issues/85) Uppgradera FastAPI/Starlette, lås beroendena (CVE-2025-62727, CVE-2026-48710) | Hög | Klart |
| [#86](https://github.com/tubalainen/varmlandsinfo/issues/86) Råd för drift bakom Nginx Proxy Manager | Medel | Klart. "Bara lokalt" gäller localhost och LAN som förut ([#93](https://github.com/tubalainen/varmlandsinfo/issues/93)) |
| [#87](https://github.com/tubalainen/varmlandsinfo/issues/87) Inga interna detaljer (Ollamas adress, undantag, sökvägar) till besökarna | Medel | Klart |
| [#88](https://github.com/tubalainen/varmlandsinfo/issues/88) Säkerhetshuvuden och strikt CSP | Låg–medel | Klart |
| [#89](https://github.com/tubalainen/varmlandsinfo/issues/89) Gränser för anropens storlek, besöksstatistiken och bildhämtningen | Medel | Klart |
| [#90](https://github.com/tubalainen/varmlandsinfo/issues/90) Fråga AI länkar bara till underlaget, bildproxyn kontrollerar serverns adress | Låg–medel | Klart |
| [#91](https://github.com/tubalainen/varmlandsinfo/issues/91) Härdad container och leveranskedja | Låg | Klart |
| [#92](https://github.com/tubalainen/varmlandsinfo/issues/92) Råd för Ollama och SearXNG (CVE-2026-7482 m.fl.) | Hög om Ollama nås från nätet | Planerat |

## Råd: nå appen från internet via Nginx Proxy Manager

Inom det egna nätverket räcker `http://<värd>:7799`. Ska appen nås från internet rekommenderas en omvänd proxy med
HTTPS i stället för att öppna port 7799 i routern. Här beskrivs Nginx Proxy Manager (NPM) i en egen container på samma
värd. Appen och NPM delar ett Docker-nät, och bara NPM tar emot trafik från internet (port 80 och 443 i routern).

### 1. Valfritt: porten bara på värden

Standardvärdet `7799` publicerar porten på alla gränssnitt (0.0.0.0), så att appen nås från hela det lokala nätverket.
Docker publicerar portar förbi värdens brandvägg (ufw och firewalld ser inte Dockers regler). Vill du att appen bara
ska nås via NPM binder du porten till värden i `.env`:

```bash
VARMLANDSINFO_PORT=127.0.0.1:7799
```

Appen nås då bara från värden själv (<http://localhost:7799>) och via NPM.

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
  för den som driftar appen (appen nekar dem redan via en proxy, det här är ett extra skydd):

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

- **Bara lokalt:** `/api/health` och `/api/refresh` svarar på localhost och det lokala nätverket (privata adresser)
  när anropet inte kommer via en proxy. Anrop via en proxy (med `X-Forwarded-For` m.fl.) och från publika adresser
  nekas.
- **Spärrar per IP-adress** (Fråga AI och lösenordet till `/besoksinfo`) litar på `X-Forwarded-For` när anropet
  kommer från en privat adress, alltså från proxyn eller från LAN.
- **Bra att känna till:** appen litar på LAN. En proxy som inte lägger till `X-Forwarded-For` (t.ex. ren
  TCP-vidarebefordran) och anrop över IPv6 till en port som Docker publicerar kan se ut att komma från LAN. Blockera
  då `/api/health` och `/api/refresh` i proxyn, eller bind porten till `127.0.0.1` enligt ovan. Den som når appen
  från LAN kan också ange en valfri adress i `X-Forwarded-For` och på så sätt komma runt spärrarna per IP-adress.
- **Utan proxy mot internet:** öppnas port 7799 direkt i routern går all trafik okrypterat, även lösenordet till
  `/besoksinfo`. Det fungerar, men HTTPS via en omvänd proxy rekommenderas.
- **Inga interna detaljer till besökarna:** fel hos Ollama visas med fasta texter, utan Ollamas adress (ofta en
  privat IP-adress), undantag eller Ollamas eget felsvar, och `/api/events` visar varken datakatalogen eller
  lagringsfelets detaljer. Allt finns i loggen och i `/api/health`.
- **Gränser:** anrop med en kropp större än 32 KB avvisas (413), både enligt `Content-Length` och medan kroppen tas
  emot. Besöksstatistiken har tak per dygn, och bildproxyn hämtar nya bilder från källorna i en begränsad takt, så att
  ingen kan fylla minnet eller disken eller få källorna att spärra appen.
- **Säkerhetshuvuden:** alla svar har `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `X-Frame-Options: DENY`, `Cross-Origin-Opener-Policy: same-origin` och en `Permissions-Policy` som stänger av
  kamera, mikrofon, position och betalning. Sidan har en strikt Content-Security-Policy: bara appens egna skript,
  stilar, bilder och anrop, inga inbäddade skript och ingen inbäddning i andra sidor. Även om någon skulle lyckas
  få in kod i en text från en källa kan webbläsaren inte köra den. HSTS sätts i den omvända proxyn, eftersom bara
  den vet om HTTPS används.
- **Fråga AI:** bara länkar till underlaget (evenemangen och webbträffarna) blir klickbara i AI:ns svar, och svar med
  andra adresser sparas inte. En evenemangstext som försöker få AI:n att länka till en falsk sida ger alltså bara text
  (se [Fråga AI](fraga-ai.md#säkerhet-och-avgränsning)).
- **Bildproxyn** hämtar bara bilder som finns i evenemangen, bara från publika adresser (kontrolleras både före och
  efter anslutningen) och bara riktiga bildfiler.
- **Beroenden:** alla beroenden är låsta till kända versioner i `app/constraints.txt`, se
  [Utveckling](utveckling.md#beroenden).
- **Containern** (`docker-compose.yaml`) startar med `no-new-privileges`, utan andra capabilities än de som
  entrypointen behöver för att ge `/data` rätt ägare och byta till `PUID:PGID`, och med skrivskyddat filsystem utom
  `/data` och `/tmp`. Appen själv kör som vanlig användare utan några capabilities. Varje bygge av imagen får
  Debians säkerhetsuppdateringar, även när basimagen inte hunnit byggas om.
- **Säkerhetskontroll varje vecka** (flödet *Säkerhetskontroll*): `pip-audit` kontrollerar de låsta
  Python-beroendena och Trivy den publicerade imagen mot kända sårbarheter. Rött betyder att något behöver
  uppdateras, oftast räcker en ny release. Kontrollen stoppar aldrig en release. Sårbarheter rapporteras enligt
  [SECURITY.md](../SECURITY.md).
- **Ingen API-dokumentation**, ingen åtkomstlogg, inga cookies, appen körs som vanlig användare i containern, och
  bilderna visas via appen så att källorna aldrig ser besökarna.

## Lösenordet till besöksstatistiken

`/besoksinfo` skyddas med HTTP Basic och `BESOKSINFO_PASSWORD`. Använd ett långt slumpat lösenord (t.ex.
`openssl rand -base64 24`), och öppna sidan via HTTPS när den nås från internet.
