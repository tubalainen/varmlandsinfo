# Källor

| Källa | Hur | Vad |
|-------|-----|-----|
| [Visit Värmland](https://visitvarmland.com/evenemang) | Öppet API (Turid v8) | Evenemang i hela Värmland. Omfattar även Karlstads och Hammarö kommuns evenemangskalendrar, som visar ett urval ur samma API. |
| [Ticketmaster](https://www.ticketmaster.se) | Discovery API v2 (kräver API-nyckel) | Konserter, shower och sport på arenor i Värmland. |
| [Karlstad CCC](https://www.karlstadccc.se/17/38/program-biljetter/) | Kalendersidan (HTML) | Konserter och shower i Solasalen. |
| [Scalateatern](https://www.scalateatern.se/forestallningar/) | Föreställningslistan (HTML) | Teater, musik och humor på Scalateaterns scener. |
| [SHL](https://www.shl.se/game-schedule) | Öppet spelschema-API | Färjestad BK:s hemmamatcher (laget går att byta med `SHL_TEAM_CODE`). |
| [Bandy (Profixio)](https://www.profixio.com/app/lx/SBF) | Svenska Bandyförbundets matcher i Profixio (HTML) | Bandymatcher i Värmland för seniorer: serier, cuper och träningsmatcher (inte ungdom). Bandy spelas på is med skridskor, inte innebandy. |
| [Handboll (Profixio)](https://www.profixio.com/app/lx/SHF) | Svenska Handbollförbundets matcher i Profixio (HTML) | Handbollsmatcher i Värmland för seniorer, herr och dam: nationella serier, Svenska cupen och Handbollförbundet Västs division 2–4 (inte ungdom, motion eller para). |
| [Great Event](https://www.greateventofkarlstad.se/kommande-evenemang/) | Sidan Kommande evenemang (HTML) | Konserter och evenemang på bland annat Löfbergs Arena, Nöjesfabriken och Julins Backyard BBQ. |
| [Karlstad Loppis](https://karlstadloppis.se/) | Startsidan (HTML) | Bakluckeloppisen på I2 Norra Fältet i Karlstad (nästa datum, söndagar 10–15). |
| [loppisar.com](https://www.loppisar.com/sokning.html) | Sökningen för Värmland (HTML) | Loppisar i Värmland med öppettider per dag, 30 dagar framåt. |
| [Svensk Bilsport (SBF)](https://www.sbf.se/tavlingar/tavlingskalender) | Tävlingskalendern LoTS (HTML) | Bilsport: folkrace, rally, rallycross, crosskart, karting, bilcross, racing, drifting … |
| [Svemo](https://ta.svemo.se) | Tävlingskalendern Svemo TA (HTML) | MC- och snöskotersport: motocross, enduro, speedway, trial … |
| [Säffle kommun](https://saffle.se/uppleva-och-gora/visit-saffle/evenemang.html) | Kommunens evenemangskalender (JSON) | Evenemang i Säffle som inte finns hos Visit Värmland: Medis, Sagabiografen, biblioteket, Silvénska villan, bygdegårdar … |
| [Kils kommun](https://kil.se/arkiv/evenemang) | Kommunens evenemangskalender (HTML) | Evenemang i Kil: biblioteket, konserter, barnaktiviteter … |
| [Skoghalls Folkets Hus](https://skoghallsfolketshus.se/) | WordPress REST-API och produktionssidorna (HTML) | Pubkvällar, konserter, teater och föreläsningar i Skoghall (Hammarö), men inte film. |

Samma evenemang från flera källor slås ihop och visas en gång, med länkar till alla källor. Källornas ordning i
tabellen är också deras prioritet vid sammanslagningen. Har en källa samma evenemang två gånger (Visit Värmland har
ibland en post från arrangören och en från lokalen) slås de ihop när dag, starttid och plats är desamma.

**Visit Värmland:** kommunen bestäms av platsens adress och namn, i andra hand av arrangörens kommun och sist av
arrangörens ort. Karlstads Riksteaterförening arrangerar till exempel föreställningar i Skoghall (Hammarö).

**Motorsport:** SBF och Svemo visas som **en** källa, *Motorsport*. Med kommer publika tävlingar och prova på-dagar i
Värmland och Karlskoga (som Visit Värmland), men inte träningstillstånd, kurser, besiktningar och tävlingar utan publik.
Kalendrarna saknar län, så läget avgörs av banans namn (t.ex. Kalvholmens Motorstadion → Karlstad, Hagforsvallen →
Hagfors) och i andra hand arrangörsklubbens ort. Radiostyrd bilsport, Drivers Open och Ticket to drive räknas inte som
evenemang.

**Bandy:** Svenska Bandyförbundets matcher finns i Profixio. Profixios API kräver en nyckel, men de publika sidorna går
att läsa. Med kommer seniormatcher (nationella serier och cuper, och distrikt Mellansveriges serier och träningsmatcher,
dit Värmland hör) som spelas i Värmland: på en värmländsk arena (t.ex. Tingvalla Isstadion → Karlstad) eller med ett
värmländskt hemmalag (lagets ort, t.ex. Slottsbron IF → Grums). Ungdoms- och juniorlag (U17, F15 …) räknas inte.
Säsongen 2026/27 är det IF Boltic (Bandyallsvenskan herr) och Slottsbron IF (träningsmatcher).

**Handboll:** Svenska Handbollförbundets matcher finns också i Profixio. Värmland hör till Handbollförbundet Väst. Med
kommer seniormatcher, herr och dam, i de nationella serierna (Handbollsligan, Allsvenskan, Dam/Herr 1, Svenska cupen)
och Västs division 2–4, när matchen spelas i Värmland: på en värmländsk arena (t.ex. Hammarhallen, Hammarö) eller med
ett värmländskt hemmalag (ort i lagnamnet eller en känd klubb, t.ex. IF Hellton → Karlstad och HK Brukspôjkera →
Forshaga). Serierna har oftast bara något enstaka lag från Värmland, så appen läser lagens egna sidor i stället för
hela seriers spelscheman. Säsongen 2026/27 är det IF Hellton Karlstad (Dam 1, Herr 2 Väst och utvecklingslaget i Dam 3
Väst), IFK Hammarö (Herr 3 Väst) och IFK Kristinehamn (Herr 4 Väst).

**Loppisar:** Karlstad Loppis och loppisar.com visas som **en** källa, *Loppisar*, i menyn, i filtret Källa, på korten
och på sidan *Om applikationen*. I bakgrunden är de fortfarande två källor, med egen hämtning, lagring och status i
`/api/health`.

**Kommunerna:** Säffles och Kils kommuner har egna evenemangskalendrar, som inte är kopplade till Visit Värmland. De
visas som **en** källa, *Kommunerna*. Säffles kalender ger datum utan år, så året räknas fram (listan har bara
tillfällen som inte är slut). Kils kalender saknar plats och kategori, så kategorierna tas ur titeln. Återkommande
tillfällen (t.ex. Babytorsdag) blir ett evenemang med flera tillfällen. Karlstads och Hammarö kommuns kalendrar
visar Visit Värmlands evenemang och behövs inte, och det gäller även Sunne (Sagolika Sunne) och Grums.

**Skoghalls Folkets Hus:** de flesta produktionerna är filmer, och sajtens kategori Bio används inte konsekvent. Med
kommer bara produktioner med en kategori som inte är film (Teater, Föreläsning, Pubkväll, konsert …) eller en titel
som börjar med till exempel Pubkväll, Teater eller Författarbesök. Sändningar på bioduken (Opera på Bio, Musikal på
Bio, André Rieu) räknas som bio och kommer inte med. Datum och tid tas ur biljettlänken på produktionssidan. Det mesta
finns också hos Visit Värmland, men pubkvällar och evenemang utanför huset (Bygdegården Svenshult, Tingvallakyrkan)
saknas ofta där. Samma evenemang hos båda slås ihop även med olika titlar, när dag, tid och lokal är desamma och
titlarna har ett ord gemensamt ("Konsert: The Hebbe Family" och "Säg det med ett leende" om The Hebbe Sisters).

**Webbsidor utan API:** Profixio (bandy och handboll), CCC, Scalateatern, Great Event, Karlstad Loppis, loppisar.com, SBF, Svemo, Säffle och Kil saknar API, så
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
| Bandy | cirka 10 | Spelschemat för serierna med lag från Värmland, bara kommande matcher: 25 matcher per sida, nästa sida med ett Livewire-anrop som i webbläsaren, 2 s paus mellan anropen. En gång i veckan dessutom tävlingslistan och första sidan av varje seniorserie (cirka 15 anrop) för att se vilka serier som har lag från Värmland. |
| Handboll | cirka 10 | Lagsidan och lagets kommande matcher (15 st, Livewire-anrop som i webbläsaren) för varje lag från Värmland, 2 anrop per lag och 2 s paus. En gång i veckan dessutom tävlingslistan och första sidan av varje seniorserie (cirka 15 anrop) för att hitta lagen. |
| Great Event | 1 | Sidan Kommande evenemang. |
| Karlstad Loppis | 1 | Startsidan med nästa datum. |
| loppisar.com | 1 | Sökningen för Värmland, 30 dagar framåt. Bilderna hämtas inte (`/images/` är spärrad i robots.txt). |
| Svensk Bilsport (SBF) | cirka 12 | Alla kommande tävlingar i Sverige, 50 per sida. Sidbyte med postback, 1,5 s paus mellan sidorna. |
| Svemo | cirka 3 | Datumfiltret fungerar inte där, så bara första sidan, sista sidan och sidorna bakåt till dagens datum läses. |
| Säffle kommun | 1 | Kalenderns lista som JSON, alla kommande tillfällen i ett anrop. |
| Kils kommun | 1–2 | Kalendersidan, 25 evenemang per sida. |
| Skoghalls Folkets Hus | cirka 14 | REST-API:t (produktionerna och kategorierna) och sidan för varje produktion som inte är film, 1 s paus mellan anropen. |

Evenemangens **bilder** hämtas inte vid uppdateringen, utan först när någon visar dem. De sparas sedan på servern,
och högst 4 bilder hämtas samtidigt. Se [Bilder via appen](data-och-integritet.md#bilder-via-appen).

Skydden gäller alla källor:

- **Vid start** används sparad data, och bara källor vars data är inaktuell hämtas.
- **`POST /api/refresh`** hämtar inte om datan är yngre än 5 minuter.
- **`REFRESH_MINUTES`** kan inte sättas tätare än 30 minuter.
- **Appen är mycket försiktig med nya försök**, så att den aldrig riskerar att bli spärrad av en källa (#76).
  Källorna uppdateras sällan, så det är bättre att vänta till nästa hämtning än att försöka igen och igen:
  - **`429 Too Many Requests`:** högst ett nytt försök, och aldrig tidigare än källan ber om (`Retry-After`, i
    sekunder eller som datum, annars 60 sekunder). Ber källan om mer än 60 sekunder, eller går värdet inte att tolka,
    görs inget nytt försök förrän vid nästa hämtning. Är kvoten nästan slut pausar hämtningen.
  - **Serverfel (HTTP 500–599):** ett nytt försök efter 60 sekunder (eller efter `Retry-After` om den anges och är
    högst 60 sekunder). Misslyckas även det visas felet för källan.
  - **`401`/`403` (nekad åtkomst):** kan betyda att nyckeln är fel eller att appen är spärrad. Källan **pausas till
    nästa morgonkörning**: den hoppas över vid `POST /api/refresh` och `REFRESH_MINUTES`, och vid morgonkörningen
    provas den en gång, utan nya försök.
  - **Andra fel** (t.ex. 404 eller nätverksfel) ger inga nya försök.
- **Om en källa fallerar vid morgonkörningen** görs två nya försök med 15 minuters mellanrum (05.15 och 05.30).
  Lyckas inte de heller tas källans gamla data bort (se [Städning](data-och-integritet.md#städning-av-inaktuell-data)),
  och källan hämtas igen först vid nästa morgonkörning (eller vid `POST /api/refresh`).
- **Om en källa fallerar vid en senare uppdatering** under dagen behålls dagens data, och inga nya försök görs förrän
  vid nästa hämtning.
- **Totalt:** en källa som är nere hela dygnet hämtas högst 3 gånger per dygn (morgonkörningen), och en som nekar
  åtkomst högst 1 gång.
- **Anrop:** antalet anrop sedan start syns som `api_calls` i `/api/health`, och status per källa under `sources`.
- **API-nycklar** loggas aldrig och syns aldrig i felmeddelanden.
