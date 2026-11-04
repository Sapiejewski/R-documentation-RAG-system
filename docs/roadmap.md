# Roadmapa

Żywy dokument: kolejność i zakres zmieniają się, gdy pojawi się lepszy pomysł albo wyniki
pokażą coś nieoczekiwanego. Bez dat — liczy się kolejność.

Zasady:
- **Najpierw mierz, potem ulepszaj.** Ulepszenia retrievalu wynikają z wyników ewaluacji, nie z przeczucia.
- **Każdy etap kończy się liczbą**, którą da się pokazać na obronie (patrz „Zysk”). Miary: [goal.md](goal.md#miary-zysku).
- **Kierunek architektury:** na hoście docelowo tylko R; Python tylko w Dockerze ([architecture.md](architecture.md)).
- Jedno zadanie = jedna sesja z Claude = jedna gałąź/commit.

## M0 — Fundamenty ✅

- [x] Pipeline: ekstrakcja R → chunking → embeddingi → Qdrant → wyszukiwanie
- [x] Ewaluacja retrievalu (hit@k, MRR)
- [x] Struktura `src/` z podpakietami, prosty Makefile (CPU/GPU), `rag check`, pytest, ruff, CLAUDE.md, docs

**Zysk:** baseline retrievalu na stringr — 16 pytań, hit@1 94%, MRR 0.938.

## M1 — Synchronizacja z biblioteką (etap przejściowy: bind mount) — must have

- [ ] Wybór biblioteki w `.env` (`R_LIBRARY`), bind mount tylko do odczytu do kontenera ekstrakcji
- [ ] Ekstrakcja bez instalowania pakietów (tylko odczyt plików)
- [ ] Manifest biblioteki: `(pakiet, Version, Built)` z plików `DESCRIPTION`
- [ ] Stan indeksu w Qdrancie: `package`, `version`, `library`, `content_hash` w payloadzie
- [ ] `rag sync`: diff manifestu z indeksem → dodaj / przeindeksuj / usuń
- [ ] Hash treści chunka (`sha256(tekst + model embeddingów + wersja chunkera)`): embedding tylko dla zmienionych chunków
- [ ] Logowanie (`logging`): co sync wykrył i zrobił
- [ ] Iteracyjnie: biblioteka systemowa (base R), potem 3 popularne pakiety, po jednym — czy reingest działa
- [ ] Testy z prawdziwym Qdrantem przez testcontainers (zamiast fałszywego serwera i plików)

**Zysk:** czas synchronizacji: pełne przeindeksowanie vs poziom pakietu vs poziom pakietu + chunków.

## M2 — Python w Dockerze + HTTP API

- [ ] Usługa `rag` w compose (ingest, search przez HTTP)
- [ ] Endpoint przyjmujący dokumentację pakietów (zamiast plików JSONL)
- [ ] Development bez `uv` na hoście jako cel (uv zostaje w obrazie)

**Zysk:** uruchomienie całego systemu jedną komendą; na hoście tylko Docker (+ R).

## M3 — Pakiet R na hoście: dynamiczna synchronizacja

- [ ] Pakiet R: manifest bibliotek z `.libPaths()`, ekstrakcja zmienionych pakietów, wysyłka do API
- [ ] Wyzwalacze: start sesji, `addTaskCallback()` (po każdej komendzie, tani test zmian), ręcznie `sync()`
- [ ] Koniec bind mountu: kontener nie dotyka dysku hosta
- [ ] Biblioteki projektów `renv` (pole `library` w Qdrancie)

**Zysk:** czas od `install.packages()` do dostępności pakietu w RAG.

## M4 — Generacja z pętlą weryfikacji

- [ ] Dokument projektowy `docs/design/verification.md` (zasady i poziomy sprawdzeń) przed kodem
- [ ] Podpakiet `rag/generation/`: prompt z kontekstem i cytowaniem źródeł (`pkg::topic`), `rag ask`
- [ ] Tabela symboli przy ekstrakcji: eksporty i argumenty funkcji danej wersji
- [ ] Weryfikacja: składnia → użyte funkcje/argumenty (parser R) → istnienie w zainstalowanej wersji
      → ugruntowanie w kontekście → opcjonalnie wykonanie w sandboxie; poprawka z konkretnym błędem, max N prób
- [ ] MLflow Tracing: ślad każdego pytania (retrieval, generacja, weryfikacja)

**Zysk:** działający asystent; ile halucynacji wyłapuje weryfikacja; koszt czasowy weryfikacji.

## M5 — Ewaluacja odpowiedzi — główne wyniki pracy

- [ ] Zbiór zadań z wykonywalnym kodem R i oczekiwanym wynikiem (`eval/answers/`)
- [ ] Pytania zależne od wersji pakietu (argumenty dodane/usunięte między wersjami)
- [ ] Porównanie: bez RAG / RAG / RAG + weryfikacja × kilka rozmiarów lokalnego modelu
- [ ] MLflow Tracking dla przebiegów; wyniki także w `results/` (JSON, w gicie)

**Zysk:** o ile RAG i weryfikacja zwiększają odsetek poprawnych odpowiedzi i zmniejszają halucynacje;
czy **mały model z RAG dorównuje dużemu bez RAG** (tańszy sprzęt, mniej pamięci, szybciej).

## M6 — Optymalizacja retrievalu

- [ ] Wybrane na podstawie M5: hybryda z BM25, reranker, inny chunking, inne embeddingi
- [ ] Każde ulepszenie jako eksperyment „przed/po”

**Zysk:** przyrost hit@k / poprawności odpowiedzi na ulepszenie, z kosztem (czas, pamięć).

## M7 — Addin RStudio

- [ ] UI na bazie pakietu R z M3: pytanie o zaznaczony kod lub ostatni błąd
- [ ] Odpowiedź w panelu (Shiny gadget) ze źródłami i wynikiem weryfikacji

**Zysk:** demo na obronę; asystent tam, gdzie programista R faktycznie pracuje.

## M8 — Badanie użyteczności

- [ ] Scenariusz zadań, kilku uczestników, z asystentem i bez
- [ ] Zamrożenie wyników

**Zysk:** czas rozwiązania zadania i odsetek rozwiązanych zadań z asystentem vs bez.

## M9 — Pisanie

## Pomysły (do rozważenia, poza planem)

- Agentowy RAG: model sam woła narzędzia (`search_docs`, `get_help`, `run_r`) — porównanie ze stałym pipeline'em.
- Serwer MCP wystawiający RAG dla dowolnego klienta MCP.
- Positron (IDE od Posit z rozszerzeniami jak VS Code) zamiast/obok addinu RStudio.
- Obserwowanie folderów biblioteki (polling) jako dodatkowy wyzwalacz synchronizacji.
