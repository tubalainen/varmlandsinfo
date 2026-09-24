# Arbetsflöde

## Issues först

Varje förändring utgår från en issue som beskriver bakgrund, krav och acceptanskriterier.
Finns ingen issue skapas en innan arbetet börjar. Issuen är baslinjen för förändringen.

## Commits direkt på main

- `main` är enda grenen och ska alltid gå att bygga och köra.
- Ändringar committas direkt på `main`. Commit-meddelandet refererar issuen (`Closes #N`).
- Kör testerna lokalt innan push. CI (tester) och Docker-bygget körs vid varje push till `main`, men
  ingen image publiceras.
- Lägg till en rad i `CHANGELOG.md` under `[Unreleased]` med issue-nummer.
- En release kan innehålla flera ändringar.

## Versionsnummer

Projektet använder [semantisk versionering](https://semver.org/lang/sv/) `MAJOR.MINOR.PATCH`:

- **PATCH**: buggfixar
- **MINOR**: ny funktionalitet som är bakåtkompatibel
- **MAJOR**: ändringar som bryter befintlig användning (t.ex. ändrade inställningar)

Så länge versionen är `0.x` kan även MINOR-steg innehålla brytande ändringar.

Versionen finns på ett ställe: `app/version.py`. Den visas i gränssnittets sidfot och i `/api/health`.

## Göra en release

Releaser görs på begäran. Images publiceras bara vid release.

1. **Välj version.** Om ingen version anges räknas nästa version fram enligt semver utifrån innehållet
   under `[Unreleased]`:
   - nya funktioner eller ändrat beteende i appen ger **MINOR** (0.0.1 → 0.1.0)
   - buggfixar och ändringar i bygg eller dokumentation ger **PATCH** (0.1.0 → 0.1.1)
   - brytande ändringar efter 1.0 ger **MAJOR**
2. **Release-commit på `main`.** Sätt versionen i `app/version.py` och flytta raderna under `[Unreleased]`
   i `CHANGELOG.md` till `## [X.Y.Z] - ÅÅÅÅ-MM-DD`, med uppdaterade jämförelselänkar längst ner.
   Pusha till `main`. Klart!

Flödet `.github/workflows/release.yml` körs vid varje push till `main`. Det gör något bara när versionen i
`app/version.py` saknar release. Då

- stoppar det om CHANGELOG saknar avsnittet för versionen,
- skapar det taggen `vX.Y.Z` och en GitHub-release med avsnittet ur CHANGELOG plus automatiskt
  genererade release notes,
- bygger och publicerar det imagen `ghcr.io/tubalainen/varmlandsinfo` med taggarna `X.Y.Z`, `X.Y` och `latest`.

Efter releasen städas repot: inga öppna PR:er eller överblivna grenar och de ingående issues är stängda.

En release kan också skapas genom att pusha en tagg (`git tag vX.Y.Z && git push origin vX.Y.Z`) eller
genom att köra flödet **Release** manuellt under *Actions*.

## Kontrollera gränssnittet i ljust och mörkt läge

Efter ändringar i gränssnittet: starta appen och kör kontrastkontrollen. Den öppnar lista, kalender,
dagsdialog och chatt i båda lägena och mäter kontrasten för all text (WCAG AA). Skärmdumparna hamnar i
`tools/screenshots/`.

```bash
npm i -g playwright            # en gång
node tools/contrast-check.mjs http://localhost:8080
```

## Köra tester lokalt

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q tests
```
