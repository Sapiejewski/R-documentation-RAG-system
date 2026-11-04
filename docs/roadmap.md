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

- [x] Wybór bibliotek w `.env` (`R_SYSTEM_LIBRARY`, `R_USER_LIBRARY`), bind mount tylko do odczytu (przejściowo)
- [x] Ekstrakcja bez instalowania pakietów (tylko odczyt plików); tryb `install` dla eksperymentów
- [x] Manifest biblioteki: `(pakiet, Version, Built)` z plików `DESCRIPTION` — porównanie bez zmian: 50 s → 1,2 s
- [ ] Usługa `rag` w Dockerze z HTTP API (FastAPI): `POST /sync` (manifest → plan), paczki stron, `commit`
- [ ] Stan indeksu w Qdrancie: `package`, `version`, `built`, `library`, `content_hash` w payloadzie
- [ ] Hash treści chunka (`sha256(tekst + model embeddingów + wersja chunkera)`): embedding tylko dla zmienionych chunków
- [ ] Spójność per pakiet: stara wersja aktualna do `commit`; przerwany transfer = ponowna prośba przy następnym syncu
- [ ] Cienki klient R (httr2): manifest → `/sync` → wysyłka paczek stron → `commit`; uruchamiany w `r-extract`
- [ ] Logowanie (`logging`) po stronie serwisu: co sync wykrył i zrobił, ile trwało
- [ ] Iteracyjnie: base R, potem data.table, stringr, dplyr (po jednym), usunięcie i reinstalacja pakietu
- [ ] Testy z prawdziwym Qdrantem przez testcontainers; testy klienta R (testthat)

**Zysk:** czas synchronizacji: pełne przeindeksowanie vs poziom pakietu vs poziom pakietu + chunków;
gdzie jest wąskie gardło (ekstrakcja w R, transport, embedding).

## M2 — Pakiet R na hoście: dynamiczna synchronizacja

- [ ] Klient R z M1 jako pakiet na hoście: manifest bibliotek z `.libPaths()`
- [ ] Wyzwalacze: start sesji, `addTaskCallback()` (po każdej komendzie, tani test zmian), ręcznie `sync()`
- [ ] Wysyłka w procesie R w tle — nie blokuje konsoli użytkownika
- [ ] Koniec bind mountu: kontener nie dotyka dysku hosta; na hoście tylko R
- [ ] Biblioteki projektów `renv` (pole `library` w Qdrancie)

**Zysk:** czas od `install.packages()` do dostępności pakietu w RAG.

## M3 — Generacja z pętlą weryfikacji

- [ ] Dokument projektowy `docs/design/verification.md` (zasady i poziomy sprawdzeń) przed kodem
- [ ] Podpakiet `rag/generation/`: prompt z kontekstem i cytowaniem źródeł (`pkg::topic`), `rag ask` i endpoint API
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
