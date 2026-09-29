# API

API:t är till för appens eget gränssnitt.

| Metod | Sökväg             | Beskrivning |
|-------|--------------------|-------------|
| GET   | `/api/events`      | Alla aktuella evenemang i JSON, sorterade på nästa tillfälle. Bildadresserna pekar på appen (`/img/…`). |
| GET   | `/besoksinfo`      | Besöksstatistiken (HTML). Bara när `BESOKSINFO_PASSWORD` är satt (annars 404), och bara med lösenordet (HTTP Basic, annars 401). Efter 10 felaktiga försök på 15 minuter 429. Se [Besöksstatistik](data-och-integritet.md#besöksstatistik). |
| GET   | `/img/<nyckel>`    | En evenemangsbild via appen. Bara bilder som finns i appens evenemang, annars 404. Se [Bilder via appen](data-och-integritet.md#bilder-via-appen). |
| GET   | `/api/health`      | Version, antal evenemang, status per källa, senaste och nästa uppdatering, lagringsstatus. **Bara lokalt.** |
| POST  | `/api/refresh`     | Hämtar alla evenemang på nytt, städar bort inaktuell data och svarar när det är klart. Hämtar inte om datan är yngre än 5 minuter. **Bara lokalt.** |
| GET   | `/api/chat/presets` | De fördefinierade frågorna i Fråga AI. |
| GET   | `/api/chat/status` | Om AI-chatten är konfigurerad och om Ollama går att nå. |
| POST  | `/api/chat`        | Ny fråga: `{"question": "…"}` med sessions-id i huvudet `X-Chat-Session`. Svaret strömmas som NDJSON och börjar med `{"type": "session", "id": …}`. 409 om en fråga redan pågår. För många frågor till AI:n (5 per 30 minuter och session, 20 per 30 minuter och IP-adress) ger en händelse `{"type": "error"}` i svaret. |
| GET   | `/api/chat/session` | Samtalet för sessionen i `X-Chat-Session`. |
| DELETE | `/api/chat/session` | Nytt samtal: tar bort sessionens historik. |

Med `CHAT_ENABLED=false` svarar alla `/api/chat*` med 404, och `chat.visible` i `/api/events` är `false`.

## Åtkomst till API:t

Det som gränssnittet hämtar (`/api/events`, `/img/…` och `/api/chat*`) kan alltid hämtas av den som når appen, även
med ett skript. Resten är begränsat:

- **Ingen API-dokumentation:** FastAPI:s `/docs`, `/redoc` och `/openapi.json` är avstängda.
- **Bara lokalt:** `/api/health` och `/api/refresh` svarar bara på anrop direkt från samma dator eller det lokala
  nätverket (localhost och privata adresser som 192.168.x.x, 10.x.x.x och 172.16–31.x.x). Övriga får 403. Dockers
  healthcheck anropar `/api/health` inifrån containern och fungerar som vanligt.
- **Omvänd proxy:** appen har ingen proxykonfiguration, det hanteras utanför appen. Anrop som kommer via en omvänd
  proxy (med huvudena `Forwarded`, `X-Forwarded-For`, `X-Real-IP`, `CF-Connecting-IP` eller `True-Client-IP`)
  räknas aldrig som lokala. Allt som når appen via proxyn nekas alltså till `/api/health` och `/api/refresh`. En
  proxy som inte sätter något av huvudena (t.ex. ren TCP-vidarebefordran) ser ut som ett lokalt anrop. Blockera
  då gärna `/api/health` och `/api/refresh` i proxyn.
- **Fråga AI:** högst 5 frågor till AI:n per 30 minuter och session och 20 per 30 minuter och IP-adress, så att
  ingen kan belasta Ollama genom att öppna nya flikar eller börja nya samtal. Frågor som besvaras utan AI
  (sökfrågor, sparade svar, stoppade frågor) räknas inte. När anropet kommer från en proxy i det lokala nätverket
  gäller spärren adressen som proxyn lagt till sist i `X-Forwarded-For`.
