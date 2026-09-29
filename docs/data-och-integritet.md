# Data och integritet

## Lagring på servern

Allt som hämtas från källorna sparas på värden i katalogen `./data` bredvid `docker-compose.yaml`. Katalogen
monteras som volym till `/data` i containern och skapas automatiskt.

| Fil                        | Innehåll |
|----------------------------|----------|
| `data/visitvarmland.json`  | Rådata från Visit Värmland (evenemang och kommuner). |
| `data/ticketmaster.json`   | Rådata från Ticketmaster (evenemang i Värmland). |
| `data/ccc.json`            | Karlstad CCC:s kalendersida. |
| `data/scala.json`          | Scalateaterns föreställningslistor. |
| `data/shl.json`            | Lagets hemmamatcher från SHL. |
| `data/greatevent.json`     | Sidan Kommande evenemang hos Great Event. |
| `data/karlstadloppis.json` | Startsidan hos Karlstad Loppis. |
| `data/loppisar.json`       | Sökresultatet för Värmland hos loppisar.com. |
| `data/sbf.json`            | Kommande bilsporttävlingar från SBF:s kalender. |
| `data/svemo.json`          | Kommande MC-tävlingar från Svemos kalender. |
| `data/chat_cache.json`     | Sparade AI-svar (fördefinierade frågor och de 10 senaste egna frågorna). |
| `data/images/`             | Evenemangens bilder, hämtade första gången någon visade dem. |

- **Vid start** läses filerna in och evenemangen visas direkt. En källa anropas bara om dess data är
  äldre än den senaste schemalagda uppdateringen, till exempel om containern varit avstängd över natten.
- **Vid uppdatering** skrivs filen atomärt (först till en temporär fil som sedan byter namn), så att
  en krasch inte lämnar en trasig fil.
- **Om en hämtning misslyckas** behålls data från samma dag, men aldrig data från före den senaste morgonkörningen.
- Eftersom rådata sparas kan en ny version av appen tolka om den utan att hämta allt på nytt.
- Filerna ägs av användaren `PUID`/`PGID` (standard 1000). Kör `id` på värden för att se dina värden
  och sätt dem i `.env`.
- Vill du lägga datan någon annanstans sätter du `VARMLANDSINFO_DATA`, till exempel `/srv/varmlandsinfo`.
- Radera en fil för att tvinga fram en ny hämtning av den källan vid nästa start.

## Städning av inaktuell data

All data som appen lagrar rensas när den blivit inaktuell. Städningen görs efter varje hämtning från källorna
(morgonkörningen, extra uppdateringar, nya försök och `POST /api/refresh`) och när appen startar, inte oftare än så.
Regeln är att data som hämtats före den senaste morgonkörningen (`DAILY_REFRESH_TIME`) varken används eller sparas.

| Vad | Rensas vid städningen |
|-----|--------|
| Källdata (`data/<källa>.json`) | Från före morgonkörningen, när källan inte kunde hämtas trots nya försök. Evenemangen tas bort ur appen och filen raderas. Källan visar ett fel och försöks igen var 30:e minut. |
| Data från avstängda källor | Direkt, till exempel Ticketmaster när API-nyckeln tagits bort. |
| Sparade AI-svar (`chat_cache.json`) | När de inte gäller dagens datum, aktuell evenemangsdata och modell. |
| Bilder (`data/images/`) | När de inte längre hör till något evenemang, liksom halvfärdiga filer från en avbruten hämtning. |
| Chattsamtal (bara i minnet) | Samtal som inte använts på 2 timmar, och alla samtal efter morgonkörningen. Vid omstart försvinner alla. |
| IP-adresser i spärren för Fråga AI (bara i minnet) | Adresser vars senaste AI-fråga är äldre än 30 minuter. Vid omstart försvinner alla. |
| Temporära filer (`*.json.tmp`) | Kvarglömda filer från en avbruten skrivning. |

Andra filer i datakatalogen rörs inte. Loggen visar vad som städades.

**Loggen:** appen loggar hämtningar, fel och städning, men aldrig besökarnas IP-adresser, frågetexter eller
API-nycklar. Webbserverns åtkomstlogg är avstängd. `docker-compose.yaml` begränsar Dockers logg till 3 filer à 10 MB,
så äldre rader roteras bort.

## Bilder via appen

Evenemangens bilder visas via appen, så att källornas bildservrar aldrig ser besökarna.

- `/api/events` ger bildadresser som `/img/<nyckel>`, där nyckeln är en hash av bildens adress hos källan.
- Första gången någon visar en bild hämtar servern den från källan och sparar den i `data/images/`. Därefter visas
  den från disk, och webbläsaren cachar den ett dygn. Högst 4 bilder hämtas samtidigt, och en bild som inte gick
  att hämta försöks igen tidigast efter en timme.
- **Ingen öppen proxy:** bara bilder som finns i appens evenemang kan hämtas. En okänd nyckel ger 404.
- **Inga anrop in i det lokala nätverket:** bara http- och https-adresser vars värd pekar på publika IP-adresser
  hämtas, och det kontrolleras även vid omdirigeringar.
- **Bara riktiga bilder:** JPEG, PNG, GIF, WebP och AVIF på högst 10 MB släpps igenom. Typen avgörs av filens innehåll,
  inte av vad servern påstår. SVG och annat innehåll stoppas.
- **Webbläsaren** får bara visa bilder från appen själv (`Content-Security-Policy: img-src 'self' data:`), och
  länkar till källorna skickar inte med att besökaren kommer från appen (`referrer`).

## Cookies och lagring hos besökaren

Appen använder inga cookies, och servern sätter inga. Sidan laddar inga externa skript, typsnitt, bilder eller
spårning. Tre små värden sparas i besökarens webbläsare:

| Lagring | Nyckel | Innehåll | Hur länge |
|---|---|---|---|
| `localStorage` | `route` | Om besökaren senast tittade på listan eller kalendern | Tills webbläsardatan rensas |
| `localStorage` | `sidebar` | Om menyn är ihopfälld eller utfälld | Tills webbläsardatan rensas |
| `sessionStorage` | `chat-session` | Samtalets slumpmässiga id i Fråga AI | Tills fliken stängs |

Samtalen i Fråga AI (frågor och svar) sparas bara i serverns minne och rensas enligt tabellen ovan.

Den som klickar på en länk till en källa hamnar förstås på källans webbplats, med de villkor som gäller där.
