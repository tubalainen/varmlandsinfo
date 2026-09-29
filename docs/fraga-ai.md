# Fråga AI

Ställ frågor om evenemangen på vanlig svenska, med förslagskort. Hur Ollama och SearXNG sätts upp står
i [Installation](installation.md#ai-chatten-med-ollama). Med `CHAT_ENABLED=false` döljs Fråga AI helt: menyvalet och
sidan försvinner, sidan Om beskriver inte AI-chatten och API:t för chatten (`/api/chat…`) svarar 404.

![Fråga AI besvarar en sökfråga direkt med en lista i datumordning](screenshots/fraga-ai.jpg)

## Direktsökning eller AI

Alla frågor behöver inte AI. Frågor som bara letar efter evenemang, som "När spelar Färjestad nästa gång?",
"Vad händer idag?" eller "Vilka konserter finns i Karlstad i oktober?", besvaras direkt av appen: den söker bland
evenemangen och listar träffarna i datumordning, med nästa tillfälle först för när-frågor. Finns sökorden inte i
något evenemang blir svaret att inga evenemang matchar (en fråga om innebandy ger alltså aldrig bandy eller annat). Det går på ett ögonblick
och fungerar även utan Ollama.

AI:n används när frågan kräver en bedömning, till exempel rekommendationer, jämförelser, personliga önskemål
("min son", "vi") eller långa frågor. Svaren strömmas, länkar till evenemangen och visar vilket underlag de bygger på.

- **Rekommendationer:** komplexa frågor fungerar, till exempel "Vilka aktiviteter skulle passa för min 8 år gamla son
  i Karlstad nu till helgen?". Ålder och ord som son, dotter och familj tolkas som barn, så barn- och
  familjeevenemang prioriteras. AI:n väljer ut 3–5 förslag och motiverar varför de passar.
- **Följdfrågor:** samtalet har ett sammanhang, så du behöver inte upprepa tidigare frågor och svar. AI:n får
  samtalets senaste frågor och svar, och underlaget börjar med evenemangen som de senaste svaren tog upp (de som
  länkades, annars hela underlaget). Följdfrågor med egna villkor, som "och på söndag då?" eller "finns det något
  gratis?", ärver datum, kommun och typ från tidigare frågor. En följdfråga som syftar tillbaka ("Vilken tid börjar
  den?", "Hur tar jag mig dit?", "Var ligger arenan?") besvaras av AI:n i stället för med en ny sökning. Utan Ollama
  visas evenemangen från förra svaret igen.
- **Underlaget:** appen skickar inte alla evenemang till modellen. För varje fråga tolkar den tidsuttryck (idag,
  i helgen, nästa vecka, 3 oktober, i oktober …), kommuner, evenemangstyper och sökord. Utifrån det väljer den ut
  de mest relevanta evenemangen (högst `CHAT_MAX_EVENTS`) och skickar dem som underlag. Modellen instrueras att
  bara svara utifrån underlaget.
- **Sparade svar:** AI-svar på fristående frågor sparas och återanvänds samma dag så länge evenemangen och modellen
  inte har ändrats. Alla fördefinierade frågor sparas, liksom de 10 senaste egna frågorna. Sparade svar delas
  mellan alla användare.

## Säkerhet och avgränsning

AI:n svarar bara på frågor om evenemangen i appen.

- **En spärr innan AI:n kopplas in** kontrollerar varje AI-fråga mot evenemangen i appen, innan SearXNG eller Ollama
  anropas. Frågor som inte rör dem stoppas med ett fast svar.
  - *Godkänd:* frågan nämner ett evenemang, en plats eller en arrangör som finns i appen ("Hur många besökare har
    Arvikamarten årligen?"). Godkänd är också en fråga om evenemang i allmänhet (typ, barn och familj, eller ord som
    evenemang, aktiviteter och tips) som inte nämner något namn som saknas i appen.
  - *Stoppad:* frågan nämner ett namn som inte finns bland appens evenemang, platser, arrangörer och kommuner
    ("Hur många besökare har Liseberg en helg under högsäsong?", "Vad händer i Göteborg?"). Stoppad är också en
    fråga som inte rör evenemang alls ("Skriv en dikt", "Hur blir vädret i morgon?").
  - Namn med flera ord ("Håkan Hellström") måste stå tillsammans i samma evenemang.
  - Följdfrågor ("och på söndag då?") godkänns om samtalet redan gäller evenemang i appen.
- Frågor om annat, som dikter, kod eller allmänna kunskapsfrågor, får ett fast svar som bestäms av servern.
  Modellen markerar sådana frågor, och servern ersätter markören innan något visas.
- Uppenbara försök att ändra AI:ns uppdrag ("ignorera dina instruktioner …") stoppas direkt, utan att modellen
  tillfrågas.
- Evenemangstexterna från källorna skickas som avgränsad data och kan inte ge modellen nya instruktioner.
- Frågor får vara högst 1000 tecken.
- **Integritet:** modellen körs i din egen Ollama, så frågorna skickas aldrig till någon AI-tjänst i molnet. Med
  webbsökning påslagen skickas frågan som sökord via SearXNG till sökmotorer på webben.

## Samtal och spärrar

Varje webbläsarflik har ett eget samtal (session), och servern äger historiken.

- Fliken får ett slumpat sessions-id av servern och sparar det i `sessionStorage`. Klienten skickar bara sin nya
  fråga, så historiken kan inte förfalskas.
- Samtalet (sammanhanget för följdfrågor) finns kvar när sidan Fråga AI laddas om. Det rensas, både på servern
  och i fliken, när du trycker *Nytt samtal* eller lämnar sidan Fråga AI (går till Evenemang, Kalender eller Om
  applikationen). En pågående fråga avbryts då. En ny flik ger ett nytt samtal.
- Samtalen finns bara i minnet. Samtal som inte använts på 2 timmar tas bort vid nästa städning (efter varje hämtning
  från källorna), och alla samtal tas bort efter morgonkörningen och vid omstart.
- Varje samtal ställer en fråga i taget.
- **Spärrar:** högst 5 frågor till AI:n per 30 minuter och samtal, och 20 per 30 minuter och IP-adress (rullande
  fönster), så att ingen kan belasta Ollama genom att öppna nya flikar eller börja nya samtal. Meddelandet säger hur
  länge man behöver vänta. Enkla sökfrågor, sparade svar och stoppade frågor räknas inte. Hur IP-adressen bestäms
  bakom en proxy står i [API](api.md#åtkomst-till-apit).
- **Kö:** högst 2 frågor körs samtidigt mot Ollama. Övriga väntar i en rättvis kö (först till kvarn, högst 10 i kö),
  och den som väntar ser sin plats i kön. Enkla sökfrågor och sparade svar går förbi kön.

## Webbsökning

Med en egen SearXNG (`SEARXNG_URL`) kan AI:n komplettera svaren med information från webben, till exempel mer om en
artist, en plats eller ett evenemang i Värmland som saknas i källorna.

- **Bara AI-frågor om ett visst evenemang, en plats eller en arrangör i appen** söker på webben. Allmänna frågor
  ("Vad passar min son i helgen?"), frågor som stoppas av spärren, direktsökningar och sparade svar gör det aldrig.
- **Sökorden** är frågan, med "Värmland" tillagt om ingen kommun nämns.
- **Träffarna** (titel, länk och utdrag, högst `SEARXNG_RESULTS`) skickas till modellen som ett avgränsat block som
  räknas som data, inte instruktioner. Evenemangen i appen går före webben, och webbuppgifter anges som
  "enligt webben" med länk.
- **Under svaret** visas träffarna i listan *Från webben*.
- **Svarar inte SearXNG** inom 8 sekunder svarar AI:n utan webben, och felet loggas.
- **Avgränsningen gäller som förut:** AI:n svarar bara på frågor om evenemang och aktiviteter i Värmland.
