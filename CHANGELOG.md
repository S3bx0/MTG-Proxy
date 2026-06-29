# Changelog

## 1.3.1 - 2026-06-29

### Changed

- Skorygowano format `standard` do typowego rozmiaru MTG 63.5×88.9 mm (2.5×3.5 cala), żeby wydruki nie wychodziły minimalnie za małe.

## 1.3.0 - 2026-06-26

### Added

- Dodano preflight jakości obrazów: `--preflight` oblicza efektywne DPI po skalowaniu do docelowego rozmiaru karty.
- Dodano `--min-dpi` z domyślnym progiem 300 DPI oraz wykrywanie silnego cropu dla `cover`.
- Dodano pole i akcję `Preflight quality` w GUI.

### Changed

- Ostrzeżenia renderowania korzystają z tej samej kalkulacji DPI co preflight.

## 1.2.0 - 2026-06-26

### Added

- Dodano `--card-format standard` dla kart MTG 63×88 mm oraz zachowano `planechase` 88×126 mm jako format domyślny.
- Dodano wybór formatu karty w GUI i zapis `card_format` do `settings.json`.
- Dodano testy dla formatów kart, walidacji GUI i eksportu PDF w formacie standardowym.

### Changed

- Ulepszono walidację nazwy pliku PDF w GUI, aby zapis pozostawał w `output/`.
- Domknięto źródłowe pliki obrazów po wczytaniu, co zapobiega kumulowaniu uchwytów przy większych batchach.

## 1.1.0 - 2026-02-20

### Added (1.1.0)

- CLI: `--suggest-back-renames` dla podglądu propozycji nazw pod tryb `strict`.
- CLI: `--write-rename-script [path]` do eksportu gotowego skryptu PowerShell `.ps1` z `Rename-Item`.
- CLI: `--apply-back-renames` (domyślnie dry-run) + `--yes` do faktycznego wykonania zmian nazw.
- CLI: `--undo-back-renames` (domyślnie dry-run) + `--yes` do cofania ostatniego batcha rename.
- CLI: `--rename-history-file [path]` do wskazania pliku historii operacji rename/undo.
- GUI: akcje `Suggest strict renames`, `Export rename .ps1`, `Apply renames (dry-run)`, `Apply renames NOW`.
- GUI: akcje `Undo renames (dry-run)` i `Undo renames NOW`.
- Testy: pokrycie flow dry-run/apply dla planu rename w `tests/test_pairing.py`.
- Testy: pokrycie flow undo (dry-run/apply) dla ostatniego batcha rename.

### Changed (1.1.0)

- Usprawniono workflow przejścia na `--back-pairing strict` przez bezpieczny etap sugestii i kontrolowanego apply.
- Uzupełniono dokumentację CLI/GUI o nowe opcje rename w `README.md`.
- Dodano trwałą historię rename (`output/rename_history.jsonl`) wykorzystywaną do rollbacku.

### Notes (1.1.0)

- Domyślne zachowanie `--apply-back-renames` nie zmienia plików (dry-run); zapis na dysk wymaga jawnego `--yes`.
- Domyślne zachowanie `--undo-back-renames` nie zmienia plików (dry-run); cofnięcie wymaga jawnego `--yes`.

## 1.0.0 - 2026-02-20

### Added (1.0.0)

- Tryb `--calibration-sheet` (2-stronicowy arkusz markerów front/back).
- Parowanie rewersów `--back-pairing` z trybami `smart` i `strict`.
- Automatyczny dobór `back_placement=auto` zależnie od orientacji strony.
- Raport zgodności front/back w GUI po generacji (`Generate + Verify`).
- Bazowe testy jednostkowe (`duplex`, `layout`, `pairing`).
- CI GitHub Actions uruchamiające `unittest` na push/PR.

### Changed (1.0.0)

- Refactor monolitu do modułów `proxgen/*` (`cli`, `config`, `layout`, `duplex`, `pairing`, `render`, `calibration`).
- `planechase_proxygen.py` działa jako cienki entrypoint kompatybilny z dotychczasowym użyciem.

### Notes (1.0.0)

- Zmiany są kompatybilne z dotychczasowym sposobem uruchamiania CLI i GUI.
