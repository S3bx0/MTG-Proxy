# MTG ProxyGen (A4 PDF)

**Wersja:** 1.3.1

Generator PDF do proxy kart MTG w dwóch formatach:

- **Planechase oversized:** 88 × 126 mm
- **Standard MTG:** 63.5 × 88.9 mm

- Wczytuje obrazy (JPG/PNG) z 2 folderów: fronty i tyły
- Układa maksymalnie dużo kart na stronie **A4** z przerwą (domyślnie 3 mm)
- Tworzy tyle stron ile trzeba
- Dla druku dwustronnego tworzy PDF w trybie **paired**: strona 1 = fronty, strona 2 = odpowiadające im tyły w tych samych miejscach

## Quick Start

1. Zainstaluj zależności:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

1. Wrzuć obrazy do folderów:

- `input/front/` – fronty kart
- `input/back/` – tyły kart (1 wspólny lub pary 1:1)

1. Wygeneruj PDF:

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --out .\output\planechase_proxies.pdf
```

## Struktura folderów

- `input/front/` – obrazy przodów kart
- `input/back/` – obrazy tyłów kart
  - jeśli wrzucisz **1** obraz, zostanie użyty jako tył dla wszystkich
  - jeśli wrzucisz **N** obrazów, muszą być w tej samej kolejności co fronty (sortowanie po nazwie pliku)
- `output/` – tu zapisze się PDF

## Instalacja

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

Przykładowe źródła grafik:

- [Moxfield deck](https://moxfield.com/decks/oedAhp4tTkqXzdxRXPCswQ)
- [Scryfall card](https://scryfall.com/card/moc/140/bloodhill-bastion)

## Struktura projektu (po refactorze)

- `planechase_proxygen.py` – cienki entrypoint CLI (wrapper)
- `gui_app.py` – web GUI (Flask)
- `proxgen/cli.py` – parser argumentów i główny flow programu
- `proxgen/config.py` – odczyt/zapis `settings.json`
- `proxgen/card_formats.py` – definicje obsługiwanych formatów kart
- `proxgen/layout.py` – obliczanie layoutu i slotów na stronie
- `proxgen/duplex.py` – mapowanie slotów rewersu (`back_placement`)
- `proxgen/pairing.py` – parowanie front/back (`smart|strict`)
- `proxgen/render.py` – właściwe renderowanie PDF z kartami
- `proxgen/calibration.py` – generowanie arkusza kalibracyjnego
- `tests/` – testy jednostkowe (`unittest`)


## Generowanie PDF

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --front-dir .\input\front --back-dir .\input\back --out .\output\planechase_proxies.pdf
```

Program automatycznie wczyta `settings.json` z katalogu projektu (jeśli istnieje).
Opcje z konsoli zawsze mają pierwszeństwo nad configiem.

Przykład dla standardowego formatu MTG:

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --card-format standard --out .\output\standard_mtg_proxies.pdf
```

## GUI (Bootstrap)

Jest też proste web-GUI z przyciskami (Bootstrap). Uruchom:

```powershell
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python .\gui_app.py
```

Potem wejdź w przeglądarce na:

- [http://127.0.0.1:5000](http://127.0.0.1:5000)

Przykład (druk z Twoją kalibracją duplex):

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py
```

Albo jawnie wskazany plik config:

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --config .\settings.json
```

Przydatne opcje:

- `--gap-mm 2` lub `--gap-mm 3`
- `--margin-mm 0` (jeśli masz drukarkę borderless) albo zostaw domyślne `5`
- `--page auto` (domyślne) – wybiera portrait/landscape tak, żeby weszło jak najwięcej kart na stronę
- `--card-format planechase` (domyślne) – Planechase oversized 88×126 mm
- `--card-format standard` – standardowa karta MTG 63.5×88.9 mm
- `--card-orientation auto` (domyślne) – dobiera portrait/landscape na podstawie obrazków frontów
- `--back-placement auto` (domyślne) – dobiera mapowanie slotów tyłu do orientacji strony (`mirror-x` dla portrait, `mirror-y` dla landscape)
- `--back-pairing smart` (domyślne) – dopasowanie tyłów do frontów po nazwie z fallbackami
- `--back-pairing strict` – wymaga jednoznacznego dopasowania nazw front/back; przy braku pary przerywa z błędem
- `--suggest-back-renames` – wypisuje propozycje nazw plików back pod `strict`
- `--write-rename-script [path]` – zapisuje gotowy skrypt PowerShell `.ps1` z komendami `Rename-Item`
- `--apply-back-renames` – wykonuje plan rename oparty o sugestie `strict`; domyślnie działa jako bezpieczny dry-run
- `--undo-back-renames` – cofa ostatni wykonany batch rename dla aktualnego `back_dir` (domyślnie dry-run)
- `--rename-history-file [path]` – plik historii operacji rename/undo (domyślnie `output/rename_history.jsonl`)
- `--yes` – użyj razem z `--apply-back-renames`, aby faktycznie wykonać rename plików
- `--back-transform rotate180` (domyślne) – jeśli u Ciebie tył wychodzi inaczej, ustaw `--back-transform none` albo `mirror-x` / `mirror-y`
- `--print-settings` – wypisuje krótką checklistę ustawień druku duplex (nie zmienia PDF)
- `--dry-run` – pokazuje wybrany layout i liczbę stron bez generowania PDF
- `--calibration-sheet` – generuje 2-stronicowy PDF kalibracyjny (markery front/back zamiast grafik)
- `--preflight` – sprawdza efektywną rozdzielczość DPI i crop bez generowania PDF
- `--min-dpi 300` – docelowa efektywna rozdzielczość dla preflight (domyślnie 300 DPI)

### Kontrola jakości DPI

Przed drukiem uruchom preflight dla tych samych opcji, z których wygenerujesz PDF:

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --card-format standard --card-orientation portrait --preflight --min-dpi 300
```

Raport liczy **efektywne DPI po dopasowaniu grafiki do fizycznego rozmiaru karty**, a nie tylko odczytuje metadane z pliku. Oznacza też obrazy z dużym cropem przy trybie `cover`.

## Duplex: szybkie ustawienia

- Jeśli tył jest w złych miejscach (nie pod kartami): zmień `--back-placement` na `same` albo `rotate180`.
- Jeśli miejsca są OK, ale grafika tyłu jest do góry nogami/odbita: ustaw `--back-transform`.
- Jeśli jest delikatny rozjazd (np. tylko góra/dół): użyj kalibracji `--back-offset-y-mm` (np. `--back-offset-y-mm 0.5`).
- Analogicznie lewo/prawo: `--back-offset-x-mm`.

### Calibration sheet (szybka kalibracja)

Wygeneruj stronę testową markerów:

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --calibration-sheet --out .\output\calibration.pdf
```

Następnie wydrukuj duplex (`100% / Actual size`) i zmierz przesunięcie markerów front/back.
Wynik wpisz jako `--back-offset-x-mm` i `--back-offset-y-mm`.

### Strict pairing helper (rename)

Podgląd sugestii nazw:

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --suggest-back-renames
```

Eksport skryptu `.ps1` z komendami rename:

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --suggest-back-renames --write-rename-script
```

Domyślnie skrypt zapisze się do `output/rename_back_files.ps1`.

Dry-run rename (nic nie zmienia na dysku):

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --suggest-back-renames --apply-back-renames
```

Wykonanie rename (zmienia nazwy plików):

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --suggest-back-renames --apply-back-renames --yes
```

Dry-run undo ostatniego batcha rename:

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --undo-back-renames
```

Wykonanie undo (cofa ostatni batch):

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --undo-back-renames --yes
```

W GUI odpowiadają za to przyciski:

- `Apply renames (dry-run)`
- `Apply renames NOW`
- `Undo renames (dry-run)`
- `Undo renames NOW`

Kalibracja jest rozdzielona na strony:

- offsety `--back-offset-*` dotyczą tylko stron z tyłami (parzyste strony w trybie `paired`)
- offsety `--front-offset-*` (domyślnie 0) dotyczą tylko stron z frontami

## Zapis kalibracji do settings.json

Jeśli dobierzesz offsety w konsoli, możesz je zapisać do pliku config jednym poleceniem:

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --back-offset-y-mm 1.98 --write-config
```

- `--write-config` bez ścieżki zapisze do `--config` (jeśli podane) albo do `settings.json` w katalogu projektu.
- Możesz też podać własną ścieżkę:

```powershell
.\.venv\Scripts\python .\planechase_proxygen.py --back-offset-y-mm 1.98 --write-config .\settings.json
```

## Notatka o rozdzielczości

Program skaluje obraz do fizycznego rozmiaru wybranego formatu karty w PDF, np. **88×126 mm** dla Planechase albo **63.5×88.9 mm** dla standardowej karty MTG.
Jeśli pliki mają mało pikseli, w konsoli pojawi się ostrzeżenie albo raport `--preflight` pokaże zbyt niskie efektywne DPI.

## Testy

Uruchomienie wszystkich testów jednostkowych:

```powershell
.\.venv\Scripts\python -m unittest discover -s .\tests -v
```

CI (GitHub Actions):

- Workflow: `.github/workflows/tests.yml`
- Uruchamia testy automatycznie na `push` i `pull request`.

## Release 1.0.0

- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Wersja CLI: `python .\planechase_proxygen.py --version`
