# Arbetsflöde

## Issues först

Varje förändring utgår från en issue som beskriver bakgrund, krav och acceptanskriterier.
Finns ingen issue skapas en innan arbetet börjar. Issuen är baslinjen för förändringen.

## Grenar och pull requests

- `main` är huvudgrenen och ska alltid gå att bygga och köra.
- Allt arbete görs i en egen gren och går in i `main` via en pull request.
- PR-beskrivningen länkar issuen med `Closes #N`, så att den stängs vid merge.
- CI (tester) och Docker-bygget ska vara gröna innan merge. Bygget på en PR publicerar ingenting.
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

Releaser görs på begäran och kan omfatta en eller flera mergade PR:er. Images publiceras bara vid release.

1. **Välj version.** Om ingen version anges räknas nästa version fram enligt semver utifrån innehållet
   under `[Unreleased]`:
   - nya funktioner eller ändrat beteende ger **MINOR** (0.0.1 → 0.1.0)
   - bara buggfixar ger **PATCH** (0.1.0 → 0.1.1)
   - brytande ändringar efter 1.0 ger **MAJOR**
2. **Release-PR.** Skapa en PR som sätter versionen i `app/version.py` och flyttar raderna under
   `[Unreleased]` i `CHANGELOG.md` till `## [X.Y.Z] - ÅÅÅÅ-MM-DD`, med uppdaterade jämförelselänkar längst ner.
3. **Merga release-PR:en.** Klart!

Flödet `.github/workflows/release.yml` körs vid varje push till `main`. Det gör något bara när versionen i
`app/version.py` saknar release. Då

- stoppar det om CHANGELOG saknar avsnittet för versionen,
- skapar det taggen `vX.Y.Z` och en GitHub-release med avsnittet ur CHANGELOG plus automatiskt
  genererade release notes (med de ingående PR:erna),
- bygger och publicerar det imagen `ghcr.io/tubalainen/varmlandsinfo` med taggarna `X.Y.Z`, `X.Y` och `latest`.

En release kan också skapas genom att pusha en tagg (`git tag vX.Y.Z && git push origin vX.Y.Z`) eller
genom att köra flödet **Release** manuellt under *Actions*.

## Köra tester lokalt

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q tests
```
