# Säkerhet

## Rapportera en sårbarhet

Hittar du en sårbarhet i Värmlandsinfo, rapportera den privat via GitHub: fliken **Security** i repot och
**Report a vulnerability**. Skriv inte om den i en öppen issue innan den är rättad.

Beskriv gärna vad som går att göra, hur det går till och vilken version det gäller (versionen står i menyn och överst
i containerns logg).

## Versioner som får rättningar

Bara den senaste releasen får säkerhetsrättningar. Uppdatera med `docker compose pull && docker compose up -d`.

Hur appen skyddar sig och råd för drift finns i [docs/sakerhet.md](docs/sakerhet.md).
