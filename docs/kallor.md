# Källor

| Källa | Hur | Vad |
|-------|-----|-----|
| [Visit Värmland](https://visitvarmland.com/evenemang) | Öppet API (Turid v8) | Evenemang i hela Värmland. Omfattar även Karlstads och Hammarö kommuns evenemangskalendrar, som visar ett urval ur samma API. |
| [Ticketmaster](https://www.ticketmaster.se) | Discovery API v2 (kräver API-nyckel) | Konserter, shower och sport på arenor i Värmland. |
| [Karlstad CCC](https://www.karlstadccc.se/17/38/program-biljetter/) | Kalendersidan (HTML) | Konserter och shower i Solasalen. |
| [Scalateatern](https://www.scalateatern.se/forestallningar/) | Föreställningslistan (HTML) | Teater, musik och humor på Scalateaterns scener. |
| [SHL](https://www.shl.se/game-schedule) | Öppet spelschema-API | Färjestad BK:s hemmamatcher (laget går att byta med `SHL_TEAM_CODE`). |
| [Great Event](https://www.greateventofkarlstad.se/kommande-evenemang/) | Sidan Kommande evenemang (HTML) | Konserter och evenemang på bland annat Löfbergs Arena, Nöjesfabriken och Julins Backyard BBQ. |
| [Karlstad Loppis](https://karlstadloppis.se/) | Startsidan (HTML) | Bakluckeloppisen på I2 Norra Fältet i Karlstad (nästa datum, söndagar 10–15). |
| [loppisar.com](https://www.loppisar.com/sokning.html) | Sökningen för Värmland (HTML) | Loppisar i Värmland med öppettider per dag, 30 dagar framåt. |
| [Svensk Bilsport (SBF)](https://www.sbf.se/tavlingar/tavlingskalender) | Tävlingskalendern LoTS (HTML) | Bilsport: folkrace, rally, rallycross, crosskart, karting, bilcross, racing, drifting … |
| [Svemo](https://ta.svemo.se) | Tävlingskalendern Svemo TA (HTML) | MC- och snöskotersport: motocross, enduro, speedway, trial … |

Samma evenemang från flera källor slås ihop och visas en gång, med länkar till alla källor. Källornas ordning i
tabellen är också deras prioritet vid sammanslagningen.

**Motorsport:** SBF och Svemo visas som **en** källa, *Motorsport*. Med kommer publika tävlingar och prova på-dagar i
Värmland och Karlskoga (som Visit Värmland), men inte träningstillstånd, kurser, besiktningar och tävlingar utan publik.
Kalendrarna saknar län, så läget avgörs av banans namn (t.ex. Kalvholmens Motorstadion → Karlstad, Hagforsvallen →
Hagfors) och i andra hand arrangörsklubbens ort. Radiostyrd bilsport, Drivers Open och Ticket to drive räknas inte som
evenemang.

**Loppisar:** Karlstad Loppis och loppisar.com visas som **en** källa, *Loppisar*, i menyn, i filtret Källa, på korten
och på sidan *Om applikationen*. I bakgrunden är de fortfarande två källor, med egen hämtning, lagring och status i
`/api/health`.

**Webbsidor utan API:** CCC, Scalateatern, Great Event, Karlstad Loppis, loppisar.com, SBF och Svemo saknar API, så
deras webbsidor läses. Ändras sidornas struktur och inga evenemang hittas, visas felet i menyn, på sidan
*Om applikationen* och i `/api/health`.

## Hur källorna anropas

Alla källor hämtas tillsammans en gång per dygn (`DAILY_REFRESH_TIME`). En normal dag blir det ungefär:

| Källa | Anrop | Kommentar |
|-------|-------|-----------|
| Visit Värmland | cirka 15 | Max 50 evenemang per sida. Kommunlistan hämtas en gång i veckan. Gräns: 60 anrop/minut. |
| Ticketmaster | 1–5 | 200 evenemang per sida. Gräns: 5 anrop/sekund, 5000 per dygn. |
| Karlstad CCC | 1 | En kalendersida. |
| Scalateatern | cirka 5 | En sida per 25 föreställningar, med paus mellan sidorna (högst 15 sidor). |
| SHL | 2 | Säsongsfilter och spelschema. |
| Great Event | 1 | Sidan Kommande evenemang. |
| Karlstad Loppis | 1 | Startsidan med nästa datum. |
| loppisar.com | 1 | Sökningen för Värmland, 30 dagar framåt. Bilderna hämtas inte (`/images/` är spärrad i robots.txt). |
| Svensk Bilsport (SBF) | cirka 12 | Alla kommande tävlingar i Sverige, 50 per sida. Sidbyte med postback, 1,5 s paus mellan sidorna. |
| Svemo | cirka 3 | Datumfiltret fungerar inte där, så bara första sidan, sista sidan och sidorna bakåt till dagens datum läses. |

Evenemangens **bilder** hämtas inte vid uppdateringen, utan först när någon visar dem. De sparas sedan på servern,
och högst 4 bilder hämtas samtidigt. Se [Bilder via appen](data-och-integritet.md#bilder-via-appen).

Skydden gäller alla källor:

- **Vid start** används sparad data, och bara källor vars data är inaktuell hämtas.
- **`POST /api/refresh`** hämtar inte om datan är yngre än 5 minuter.
- **`REFRESH_MINUTES`** kan inte sättas tätare än 30 minuter.
- **Om en källa svarar `429 Too Many Requests`** väntar appen enligt `Retry-After`. Är kvoten nästan
  slut pausar hämtningen.
- **Om en källa fallerar vid morgonkörningen** görs två nya försök med 5 minuters mellanrum. Lyckas inte
  de heller tas källans gamla data bort (se [Städning](data-och-integritet.md#städning-av-inaktuell-data)), och källan
  försöks igen var 30:e minut.
- **Om en källa fallerar vid en senare uppdatering** under dagen behålls dagens data, och källan försöks igen efter
  30 minuter.
- **Anrop:** antalet anrop sedan start syns som `api_calls` i `/api/health`, och status per källa under `sources`.
- **API-nycklar** loggas aldrig och syns aldrig i felmeddelanden.
