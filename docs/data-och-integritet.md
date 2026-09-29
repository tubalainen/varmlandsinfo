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
| `data/bandy.json`          | Kommande bandymatcher från Profixio och vilka serier som har lag från Värmland. |
| `data/greatevent.json`     | Sidan Kommande evenemang hos Great Event. |
| `data/karlstadloppis.json` | Startsidan hos Karlstad Loppis. |
| `data/loppisar.json`       | Sökresultatet för Värmland hos loppisar.com. |
| `data/sbf.json`            | Kommande bilsporttävlingar från SBF:s kalender. |
| `data/svemo.json`          | Kommande MC-tävlingar från Svemos kalender. |
| `data/saffle.json`         | Kommande evenemang i Säffle kommuns kalender. |
| `data/kil.json`            | Kommande evenemang i Kils kommuns kalender. |
| `data/chat_cache.json`     | Sparade AI-svar (fördefinierade frågor och de 10 senaste egna frågorna). |
| `data/images/`             | Evenemangens bilder, hämtade första gången någon visade dem. |
| `data/besoksinfo.json`     | Besöksstatistiken, när den är påslagen (se nedan). |
| `data/geoip/`              | DB-IP:s geodatabas för besöksstatistiken, när den är påslagen. |

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
| Chattsamtal (bara i minnet) | Direkt vid *Nytt samtal* och när man lämnar sidan Fråga AI. Annars samtal som inte använts på 2 timmar (t.ex. när fliken stängts), och alla samtal efter morgonkörningen. Vid omstart försvinner alla. |
| IP-adresser i spärren för Fråga AI (bara i minnet) | Adresser vars senaste AI-fråga är äldre än 30 minuter. Vid omstart försvinner alla. |
| Besöksstatistikens besökare med IP-adresser (`besoksinfo.json`) | Dygn som är slut: de summeras och IP-adresserna tas bort. |
| Besöksstatistikens summerade dagar | Dagar äldre än 13 månader. |
| IP-adresser i spärren för inloggningen till `/besoksinfo` (bara i minnet) | Adresser vars senaste felaktiga försök är äldre än 15 minuter. |
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

## Besöksstatistik

Besöksstatistiken är avstängd som standard. Den slås på med ett lösenord i `BESOKSINFO_PASSWORD` och visas på den dolda
sidan `/besoksinfo`, som skyddas av lösenordet (webbläsarens inloggningsruta) och inte länkas från appen. Efter 10
felaktiga lösenord på 15 minuter spärras IP-adressen en stund.

- **Vad som räknas:** sidvisningar av appen. Kända robotar och sidan `/besoksinfo` räknas inte.
- **Unika besökare** räknas per dygn utan cookies: en hash av IP-adress och webbläsare med ett slumpvärde som byts varje
  dygn. Samma person räknas en gång per dygn, men kan inte följas mellan dygnen.
- **Dagens besökare** sparas med IP-adress, tid, antal visningar, plats (land, region och ort), enhet, webbläsare,
  operativsystem och hänvisning (bara domänen på webbplatsen besökaren kom från). När dygnet är slut summeras det vid
  nästa städning, och IP-adresserna och slumpvärdet tas bort.
- **Summerad statistik per dag** (antal visningar och unika, samt fördelningen på land, ort, enhet, webbläsare,
  operativsystem och hänvisning, utan IP-adresser) sparas i 13 månader.
- **Plats** slås upp lokalt i DB-IP:s fria databas *IP to City Lite* ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
  [DB-IP](https://db-ip.com)). Databasen hämtas från db-ip.com när den saknas och sedan en gång i månaden. Inga uppgifter
  om besökarna skickas ut.
- **Bakom en omvänd proxy** används adressen som proxyn lagt till sist i `X-Forwarded-For` (se [API](api.md#åtkomst-till-apit)).
- Webbserverns åtkomstlogg är fortfarande avstängd. Statistiken finns bara i `data/besoksinfo.json`.

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
