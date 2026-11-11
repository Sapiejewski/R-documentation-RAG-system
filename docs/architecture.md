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
- Klient R (M1) działa w kontenerze `r-extract` i rozmawia z serwisem przez ten sam HTTP API co docelowo
  (w budowie: na razie zapisuje jeszcze pliki `data/extracted/`).
- Biblioteki hosta (od M1): **bind mount tylko do odczytu** do kontenera `r-extract`.
  To **rozwiązanie przejściowe**: folder jest ustalany przy starcie compose i nie da się go zmienić
  dynamicznie, a kontener nie wie, kiedy użytkownik coś zainstalował.

## Dlaczego ekstrakcja działa między wersjami R

Ekstrakcja **nie ładuje pakietów**, tylko czyta pliki: skompilowaną bazę pomocy (`help/*.rdb`)
i `DESCRIPTION`. Sprawdzone: R 4.5.1 w kontenerze poprawnie czyta i renderuje dokumentację
pakietów zainstalowanych przez R 4.3.3 na hoście (stats, utils, tools). Wersja R, kod C
i zależności pakietu nie mają znaczenia.
