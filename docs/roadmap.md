# Roadmapa

Żywy dokument: kolejność i zakres zmieniają się, gdy pojawi się lepszy pomysł albo wyniki
pokażą coś nieoczekiwanego. Bez dat — liczy się kolejność.

Zasady:
- **Najpierw mierz, potem ulepszaj.** Ulepszenia retrievalu wynikają z wyników ewaluacji, nie z przeczucia.
- **Każdy etap kończy się liczbą**, którą da się pokazać na obronie (patrz „Zysk”). Miary: [goal.md](goal.md#miary-zysku).
- **Kierunek architektury:** na hoście docelowo tylko R; Python tylko w Dockerze ([architecture.md](architecture.md)).
- **Logging i observability to cel całego projektu, nie jeden etap.** Każda nowa funkcja od
  początku loguje, co zrobiła (`logging`), a od M3 każdy krok pytania jest też śledzony
  (MLflow: ślady i eksperymenty). Ma być zawsze widać, co system robi, ile to trwa i dlaczego.
- Jedno zadanie = jedna gałąź = jeden lub kilka małych commitów.

## M0 — Fundamenty ✅

- [x] Pipeline: ekstrakcja R → chunking → embeddingi → Qdrant → wyszukiwanie
- [x] Ewaluacja retrievalu (hit@k, MRR)
- [x] Struktura `src/` z podpakietami, prosty Makefile (CPU/GPU), `rag check`, pytest, ruff, dokumentacja w `docs/`

**Zysk:** baseline retrievalu na stringr — 16 pytań, hit@1 94%, MRR 0.938.

## M1 — Synchronizacja bibliotek przez HTTP API — must have

Od razu docelowy protokół (bez plików pośrednich): cienki klient R wysyła tylko to, o co poprosi serwis.

- [x] Pierwsze uruchomienie jednym poleceniem: `make init` / `.\init.ps1` — bootstrap szuka R (instalacja tylko za zgodą), reszta w R: kontrole z naprawami, wybór bibliotek, start usług; `make doctor` — te same kontrole jako raport ([setup.md](setup.md))
- [x] Wybór bibliotek: `init` pyta (domyślnie `.libPaths()`, plus dowolne foldery), zapis `RDOCS_LIBRARIES`; biblioteka identyfikowana ścieżką
- [x] Klient R na hoście (`make sync`) — koniec bind mountów; tryb docker (`make sync-docker`) dla osób bez R i jako stały korpus do ewaluacji
- [x] `GET /health` raportuje stan Qdranta, Ollamy i pobranych modeli (widzi to `doctor`, później addin)
- [ ] Sprawdzić `init.ps1` i cały przepływ na Windowsie; sprawdzić przepływ na macOS
- [x] Ekstrakcja bez instalowania pakietów (tylko odczyt plików); tryb `install` dla eksperymentów
- [x] Manifest biblioteki: `(pakiet, Version, Built)` z plików `DESCRIPTION` — porównanie bez zmian: 50 s → 1,2 s
- [x] Usługa `rag` w Dockerze z HTTP API (FastAPI): `POST /sync` (manifest → plan), `begin`, paczki stron, `commit`, `GET /health`; schematy i dokumentacja pod `/docs`
- [x] Stan indeksu w Qdrancie: rejestr pakietów (kolekcja bez wektorów) + `library`, `built`, `generation`, `content_hash`, `active` w payloadzie chunków
- [x] Hash treści chunka (`sha256(tożsamość embeddera + tekst)`): embedding tylko dla nowych tekstów, wektory reszty kopiowane z Qdranta
- [x] Spójność per pakiet (logika `Indexer` + testy): stara wersja aktywna do `commit`; przerwany transfer = ponowna prośba przy następnym syncu
- [x] Cienki klient R (httr2): manifest → `/sync` → wysyłka paczek stron → `commit`; bez plików pośrednich
- [x] Logowanie (`logging`, poziom z `LOG_LEVEL`): `Indexer` loguje plan i commit
- [x] Logowanie każdego żądania API: metoda, ścieżka, status, czas (`make logs`); błędy walidacji jako WARNING, niedostępna Ollama/Qdrant jako 503 + ERROR
- [x] Próba end-to-end (R → API → Ollama → Qdrant) na 3 małych pakietach: pierwszy sync 27 s, bez zmian 1,5 s, usunięcie pakietu działa; wąskie gardło to embedding (11,6 z 12 s pakietu tcltk na CPU)
- [x] Porządek testów według poziomu, każdy poziom w swoim katalogu `tests/<poziom>/` (Python i R razem):
  - **unit** — logika bez I/O (chunking, `rdtext`, schematy, `Indexer` na `MemoryStore`, metryki; R: czytanie pakietów); `make test-unit`, sekundy
  - **integration** (infrastruktura) — prawdziwe usługi: Qdrant przez testcontainers, klienci HTTP na `FakeOllama`, CLI
  - **contract** (kontrakty API) — API przez `TestClient` (statusy, walidacja) i klient R na fałszywym API;
    wspólne przykłady żądań (`tests/contract/examples/`) sprawdzane po obu stronach
  - **e2e** — cały stos: R → API → Ollama → Qdrant (instalacja, sync, ponowny sync, odinstalowanie); `make test-e2e`, ok. 30 s
  - `make test` = unit + integration + contract (Python i R); od teraz każda nowa funkcja dostaje testy na odpowiednich poziomach
- [ ] Zmiana kodu czytającego pakiety w R (np. poprawka renderowania) nie wymusza ponownego wysłania
      pakietów — dziś trzeba `forget` + sync; wersja ekstraktora powinna być częścią formatu indeksu
- [x] Biblioteka, której już nie ma (usunięty projekt `renv`, stara wersja R): znika z indeksu przy najbliższym syncu; tylko biblioteki własnego pochodzenia (`host:<komputer>` / `docker`); niewybrana, ale istniejąca — `forget` ręcznie
- [ ] Iteracyjnie: base R, potem data.table, stringr, dplyr (po jednym), usunięcie i reinstalacja pakietu
- [x] Testy z prawdziwym Qdrantem przez testcontainers (zamiast fałszywego serwera HTTP)
- [x] Testy klienta R (testthat, `make test-r`): pola stron = schemat API, kolejność rozmowy, paczki, błąd jednego pakietu nie zatrzymuje reszty; kontrole i pytania `init`; e2e w obu trybach

**Zysk:** czas synchronizacji: pełne przeindeksowanie vs poziom pakietu vs poziom pakietu + chunków;
gdzie jest wąskie gardło (ekstrakcja w R, transport, embedding).

## Punkt kontrolny: demo dla promotora — najbliższy cel

Pokazać działający przepływ i **pierwszą odpowiedź na pytanie badawcze** (czy RAG poprawia
odpowiedzi), a potem ustalić z promotorem kierunek dalszych prac (metodologia M4, zakres M6).

- [ ] M1 na żywo: base R, potem data.table, stringr, dplyr; czasy pierwszego syncu, syncu bez zmian, nowego pakietu
  - [x] tryb docker (CPU): stringr, dplyr, data.table + zależności = 11 pakietów, 386 stron, 1183 chunki;
        pierwszy sync 5 min 29 s (embedding ok. 3,6 chunka/s, prawie cały czas), **bez zmian 2,7 s**
  - [ ] tryb host (po `make init`): base R i biblioteka osobista; instalacja nowego pakietu → sync
- [x] `rag ask` z przełącznikiem `--no-rag`: odpowiedź z kontekstem dokumentacji i przypisami (`pkg::topic`)
      vs sam model — wycinek M3 bez pętli weryfikacji. Pierwszy przykład: `reframe()` (dplyr 1.1) —
      bez RAG model zmyśla działanie i argument, z RAG odpowiada zgodnie z dokumentacją i ją cytuje
- [ ] Zestaw ok. 10 pytań, w których wersja pakietu ma znaczenie (nowe/zmienione funkcje); tabela z RAG / bez RAG
- [ ] `docs/demo.md`: scenariusz pokazu, przygotowanie (rozgrzanie modeli), pytania do promotora

**Zysk:** pierwsza mierzalna różnica „z RAG / bez RAG” na przykładach, które pokazują wyróżnik
projektu (zainstalowane wersje); decyzje promotora co do metodologii przed M4.

## M2 — Pakiet R na hoście: dynamiczna synchronizacja

- [ ] Klient R z M1 jako pakiet R (`rdocs`): `setup()`, `doctor()`, `sync()`; konfiguracja w `tools::R_user_dir()` zamiast `.env`
- [ ] Wyzwalacze: start sesji, `addTaskCallback()` (po każdej komendzie, tani test zmian), ręcznie `sync()`
- [ ] Wysyłka w procesie R w tle — nie blokuje konsoli użytkownika
- [ ] Biblioteki projektów `renv` (pole `library` w Qdrancie)

**Zysk:** czas od `install.packages()` do dostępności pakietu w RAG.

## M3 — Generacja z pętlą weryfikacji

- [ ] Dokument projektowy `docs/design/verification.md` (zasady i poziomy sprawdzeń) przed kodem
- [ ] Endpoint API dla pytań (`POST /ask`) — `rag ask` z punktu kontrolnego jako CLI
- [ ] Tabela symboli przy ekstrakcji: eksporty i argumenty funkcji danej wersji
- [ ] Weryfikacja: składnia → użyte funkcje/argumenty (parser R) → istnienie w zainstalowanej wersji
      → ugruntowanie w kontekście → opcjonalnie wykonanie w sandboxie; poprawka z konkretnym błędem, max N prób
- [ ] MLflow Tracing: ślad każdego pytania (retrieval, generacja, weryfikacja)

**Zysk:** działający asystent; ile halucynacji wyłapuje weryfikacja; koszt czasowy weryfikacji.

## M4 — Ewaluacja odpowiedzi — główne wyniki pracy

- [ ] Zbiór zadań z wykonywalnym kodem R i oczekiwanym wynikiem (`eval/answers/`)
- [ ] Pytania zależne od wersji pakietu (argumenty dodane/usunięte między wersjami)
- [ ] Porównanie: bez RAG / RAG / RAG + weryfikacja × kilka rozmiarów lokalnego modelu
- [ ] MLflow Tracking dla przebiegów; wyniki także w `results/` (JSON, w gicie)

**Zysk:** o ile RAG i weryfikacja zwiększają odsetek poprawnych odpowiedzi i zmniejszają halucynacje;
czy **mały model z RAG dorównuje dużemu bez RAG** (tańszy sprzęt, mniej pamięci, szybciej).

## M5 — Optymalizacja retrievalu

- [ ] Wybrane na podstawie M4: hybryda z BM25, reranker, inny chunking, inne embeddingi
- [ ] Każde ulepszenie jako eksperyment „przed/po”

**Zysk:** przyrost hit@k / poprawności odpowiedzi na ulepszenie, z kosztem (czas, pamięć).

## M6 — Addin RStudio

- [ ] UI na bazie pakietu R z M2: pytanie o zaznaczony kod lub ostatni błąd
- [ ] Odpowiedź w panelu (Shiny gadget) ze źródłami i wynikiem weryfikacji

**Zysk:** demo na obronę; asystent tam, gdzie programista R faktycznie pracuje.

## M7 — Badanie użyteczności

- [ ] Scenariusz zadań, kilku uczestników, z asystentem i bez
- [ ] Zamrożenie wyników

**Zysk:** czas rozwiązania zadania i odsetek rozwiązanych zadań z asystentem vs bez.

## M8 — Pisanie

## Pomysły (do rozważenia, poza planem)

- Agentowy RAG: model sam woła narzędzia (`search_docs`, `get_help`, `run_r`) — porównanie ze stałym pipeline'em.
- Serwer MCP wystawiający RAG dla dowolnego klienta MCP.
- Positron (IDE od Posit z rozszerzeniami jak VS Code) zamiast/obok addinu RStudio.
- Obserwowanie folderów biblioteki (polling) jako dodatkowy wyzwalacz synchronizacji.
- Równoległa wysyłka paczek z klienta R — tylko jeśli pomiary z M1 pokażą, że to wąskie gardło.
