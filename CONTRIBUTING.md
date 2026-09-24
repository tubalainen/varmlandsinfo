# Arbetsflöde

## Issues först

Varje förändring utgår från en issue som beskriver bakgrund, krav och acceptanskriterier.
Finns ingen issue skapas en innan arbetet börjar. Issuen är baslinjen för förändringen.

## Grenar och pull requests

- `main` är huvudgrenen och ska alltid gå att bygga och köra.
- Allt arbete görs i en egen gren och går in i `main` via en pull request.
- PR-beskrivningen länkar issuen med `Closes #N`, så att den stängs vid merge.
- CI (tester) och Docker-bygget ska vara gröna innan merge.
- Lägg till en rad i `CHANGELOG.md` under `[Unreleased]` med issue-nummer.
- En release kan innehålla flera PR:er.

## Versionsnummer

Projektet använder [semantisk versionering](https://semver.org/lang/sv/) `MAJOR.MINOR.PATCH`:

- **PATCH**: buggfixar
- **MINOR**: ny funktionalitet som är bakåtkompatibel
- **MAJOR**: ändringar som bryter befintlig användning (t.ex. ändrade inställningar)

Så länge versionen är `0.x` kan även MINOR-steg innehålla brytande ändringar.

Versionen finns på ett ställe: `app/version.py`. Den visas i gränssnittets sidfot och i `/api/health`.

## Göra en release

1. Skapa en PR som
   - sätter den nya versionen i `app/version.py`
   - flyttar raderna under `[Unreleased]` i `CHANGELOG.md` till ett nytt avsnitt `## [X.Y.Z] - ÅÅÅÅ-MM-DD`
     och uppdaterar jämförelselänkarna längst ner
2. Merga PR:en till `main`.
3. Tagga merge-commiten och pusha taggen:
   ```bash
   git checkout main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
   Alternativt: kör flödet **Release** manuellt under *Actions* och ange versionen. Då skapas taggen på `main`.

Flödet `.github/workflows/release.yml`

- stoppar om taggen inte stämmer med `app/version.py` eller om CHANGELOG saknar avsnittet,
- skapar en GitHub-release med avsnittet ur CHANGELOG plus automatiskt genererade release notes,
- bygger och publicerar imagen `ghcr.io/tubalainen/varmlandsinfo` med taggarna `X.Y.Z`, `X.Y` och `latest`.

Varje push till `main` publicerar dessutom en `edge`-image med det senaste från `main`.

## Köra tester lokalt

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q tests
```
