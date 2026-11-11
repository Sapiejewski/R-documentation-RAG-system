# Architektura: stan obecny i docelowy

Pojęcia (terminologia R): **pakiet** = np. `stringr`; **biblioteka** = folder z zainstalowanymi
pakietami (np. `/usr/lib/R/library`, `~/R/<platforma>/<wersja>`, biblioteka projektu `renv`).
`.libPaths()` w R wypisuje biblioteki danej sesji.

## Docelowo

Na hoście użytkownika **tylko R** (i ewentualnie RStudio). Wszystko inne w Dockerze.

```
HOST (R użytkownika)                                DOCKER
┌──────────────────────────────────┐               ┌──────────────────────────────────┐
│ pakiet R (projektu)              │   HTTP API    │ rag (Python): ingest, search,    │
│  • manifest bibliotek            │ ────────────► │   ask, weryfikacja               │
│  • wykrywanie zmian:             │               │ Qdrant: indeks + stan indeksu    │
│    start sesji, addTaskCallback, │ ◄──────────── │ Ollama: embeddingi + generacja   │
│    ręcznie sync()                │  odpowiedzi   │ MLflow: ślady i eksperymenty     │
│  • ekstrakcja zmienionych pak.   │               │ sandbox R: wykonanie kodu        │
│  • addin RStudio (UI)            │               └──────────────────────────────────┘
└──────────────────────────────────┘
```

Przepływ „dynamiczny”: użytkownik instaluje pakiet → po zakończeniu komendy callback w sesji R
wykrywa zmianę biblioteki → ekstrakcja tylko zmienionych pakietów → wysłanie do API → reingest
→ nowy pakiet jest dostępny w RAG. Serwis w Dockerze nigdy nie dotyka dysku hosta.

## Obecnie (development)

- Serwis `rag` (HTTP API, `src/rag/api/`) działa już w Dockerze (`make up`). Komendy `rag search`,
  `evaluate`, `check` i testy działają jeszcze na hoście przez `uv` (wygodny development) —
  **do przeniesienia** w kolejnych etapach roadmapy; docelowo Python tylko w Dockerze.
- Klient R (`src/client/`) działa już **na hoście**, w R użytkownika (`make sync`), z tym samym
  HTTP API co docelowo. Pliki: `config.R` (`.env`, wybrane biblioteki), `extract.R` (czytanie
  pakietów), `api.R` (rozmowa z API), `setup.R` (`init`, `doctor`), `main.R` (polecenia).
  Brakuje jeszcze tylko opakowania w pakiet R i wyzwalaczy (M2).
- Biblioteki wybiera użytkownik w `init` (domyślnie `.libPaths()`); kontener nie dotyka dysku hosta.
- Ten sam klient działa też w kontenerze `r-extract` (tryb docker) — dla osób bez R i jako stały
  korpus do ewaluacji. Przepływ na każdym systemie: [setup.md](setup.md).

## Dlaczego ekstrakcja działa między wersjami R

Ekstrakcja **nie ładuje pakietów**, tylko czyta pliki: skompilowaną bazę pomocy (`help/*.rdb`)
i `DESCRIPTION`. Sprawdzone: R 4.5.1 w kontenerze poprawnie czyta i renderuje dokumentację
pakietów zainstalowanych przez R 4.3.3 na hoście (stats, utils, tools). Wersja R, kod C
i zależności pakietu nie mają znaczenia.
