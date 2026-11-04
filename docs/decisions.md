# Dziennik decyzji

Krótko: co, dlaczego, jakie alternatywy. Najnowsze na górze. Przyda się przy pisaniu
rozdziału o implementacji.

## 2026-11 — Pydantic dla danych na granicach (`rag/schemas.py`)

Modele, które przekraczają granicę systemu — manifest od klienta R (`Installation`), wpis rejestru
(`IndexedPackage`), odpowiedzi sync (`SyncPlan`, `StoreReport`) — to modele pydantic w jednym pliku.
FastAPI waliduje nimi żądania bez dodatkowego kodu: brakujące, puste lub nieznane pole (np. literówka
w kliencie R) to od razu czytelny błąd 422, zanim ruszy nasza logika. Modele są niemutowalne
(`frozen`) i porównywane po wartości — `plan` porównuje zgłoszoną instalację z zapisaną zwykłym `==`.
Wewnętrzne typy, które nie wychodzą poza proces (`Chunk`, `Point`, `Hit`), zostają dataclassami.

## 2026-11 — Synchronizacja od razu przez HTTP API, bez plików pośrednich (dawne M1 + M2)

Pierwotnie M1 miał zapisywać całe biblioteki do `data/extracted/*.jsonl`, a API miało przyjść później.
Odrzucone: pliki to praca do wyrzucenia, puchną przy dużych bibliotekach i wymagają sztuczek
(`.partial`), żeby przerwana ekstrakcja nie wyglądała na kompletną. Zamiast tego od razu protokół docelowy:

1. Klient R → `POST /sync` z manifestem `(pakiet, version, built)` biblioteki (kilka KB).
2. Serwis porównuje ze stanem w Qdrancie i odpowiada planem: które pakiety wysłać, które usunął,
   jaki rozmiar paczki.
3. Dla każdego pakietu z planu: `begin` → paczki stron pomocy → `commit`. Do `commit` aktualna jest
   stara wersja; przerwany transfer = serwis poprosi o pakiet przy następnym syncu.
4. Paczki są idempotentne (stabilne id chunków + `content_hash`), więc ponowienie jest bezpieczne.

Endpoint odpowiada dopiero po zapisaniu paczki — naturalny backpressure (gdy embedding nie nadąża,
klient czeka) bez kolejki zadań i odpytywania o status. W M2 ten sam klient R trafia na hosta;
zniknie tylko bind mount.

## 2026-11 — Cienki klient R, gruby serwis Python

Autor projektu nie zna dobrze R, a kod musi rozumieć i obronić. Dlatego R robi tylko to, czego nie
zrobi nic innego: (1) wypisuje zainstalowane pakiety (`DESCRIPTION`), (2) zamienia skompilowaną bazę
pomocy (`help/*.rdb`, wewnętrzny format R) na tekst; od M3 także tabela symboli. Wszystkie decyzje —
co wysłać, rozmiar paczek, chunking, hashe, embeddingi, spójność, usuwanie, logowanie — w Pythonie.
Klient R wykonuje polecenia serwisu. Budżet: ok. 100–150 linii, styl „jak Python” (funkcje, `for`,
listy), testy `testthat` jako specyfikacja. Bez równoległości w R — najpierw pomiar wąskiego gardła.

Chunking zostaje w Pythonie także dlatego, że to zmienna eksperymentalna (M5): zmiana strategii nie może
wymagać aktualizacji kodu u użytkownika ani ponownej ekstrakcji wszystkich pakietów.

Zależności: **FastAPI** (async, walidacja danych wejściowych, dokumentacja API pod `/docs`),
**httr2** w R (ponawianie żądań, gzip). Obie dają realną funkcjonalność, nie są cienkimi nakładkami.

## 2026-11 — Synchronizacja bibliotek: docelowo z hosta, dynamicznie

- **Cel:** użytkownik instaluje pakiet na hoście → reingest wyzwala się sam → pakiet jest w RAG.
- **Docelowo (M2):** pakiet R na hoście wykrywa zmiany (start sesji, `addTaskCallback()` po każdej
  komendzie, ręczne `sync()`), sam robi ekstrakcję zmienionych pakietów i wysyła je do API w Dockerze.
  R nie ma haka „po instalacji”, ale callback sprawdza stan biblioteki, więc działa dla
  `install.packages`, `pak` i `renv` jednakowo. Serwis w Dockerze nie dotyka dysku hosta.
- **Przejściowo (M1):** bind mount wybranych bibliotek (`R_SYSTEM_LIBRARY`, `R_USER_LIBRARY` w `.env`)
  tylko do odczytu; klient R działa w kontenerze `r-extract`.
  Nie jest docelowy: folder jest ustalany przy starcie compose i nie da się go zmienić dynamicznie,
  a kontener nie wie, kiedy coś zainstalowano.
- Odrzucone: ekstrakcja przez R hosta wywoływana z Pythona na hoście (łamie „Python tylko w Dockerze”).
- Sprawdzone: R 4.5.1 w kontenerze czyta dokumentację pakietów zainstalowanych przez R 4.3.3,
  bo ekstrakcja tylko czyta pliki (`help/*.rdb`, `DESCRIPTION`), nie ładuje pakietów.

## 2026-11 — Wykrywanie zmian: hash wejścia, nie wektora; stan w Qdrancie

- Hash wektora nic nie daje: żeby go policzyć, trzeba najpierw policzyć embedding — najdroższy krok.
  Wektor jest deterministyczną funkcją wejścia, więc hashujemy wejście.
- **Poziom pakietu:** manifest `(pakiet, Version, Built)` z `DESCRIPTION`. `Built` zmienia się przy
  każdej reinstalacji (też tej samej wersji, np. z GitHuba). Niezmienione pakiety pomijane w całości.
- **Poziom chunka:** `content_hash = sha256(tekst + model embeddingów + wersja chunkera)` w payloadzie.
  Embedding tylko dla nowych hashy. Zmiana modelu lub chunkera sama wymusza pełne przeliczenie.
- **Stan indeksu w Qdrancie** (payload: `package`, `version`, `library`, `content_hash`), nie w pliku —
  jedno źródło prawdy, nie może się rozjechać z indeksem.
- Jedna kolekcja dla wszystkich bibliotek, rozróżnianych polem `library` (decyzja do potwierdzenia przy `renv`).

## 2026-11 — Python docelowo tylko w Dockerze; na hoście tylko R

Na czas developmentu Python działa na hoście przez `uv`. Kolejne etapy (M1: usługa `rag` w compose
z HTTP API, M2: pakiet R na hoście) mają usunąć tę potrzebę — użytkownik instaluje tylko R
(+ ewentualnie RStudio) i Docker.

## 2026-11 — Testy z prawdziwym Qdrantem przez testcontainers

Docelowo testy integracyjne używają prawdziwego Qdranta w kontenerze (testcontainers) zamiast
fałszywego serwera HTTP i plików JSONL na dysku. Czysta logika (parsowanie Rd, chunking, diff
manifestów) nadal testowana bez Dockera — szybko. Ollama w testach zostaje zastąpiona
deterministycznym `FakeEmbedder` (prawdziwy model to minuty pobierania i niedeterminizm).

## 2026-11 — Weryfikacja odpowiedzi: zasady

Szczegóły w `docs/design/verification.md` (M3). Zasady: najpierw sprawdzenia deterministyczne,
LLM tylko do poprawek; źródło prawdy = zainstalowana wersja; ograniczona pętla (max N poprawek,
limity czasu); kod modelu wykonywany wyłącznie w izolowanym sandboxie, nigdy automatycznie
w sesji użytkownika; każde sprawdzenie daje ustrukturyzowany wynik (metryki); użytkownik widzi,
co sprawdzono i poprawiono. Wydobywanie funkcji i argumentów parserem R, nie regexem.

## 2026-11 — Observability: logging + MLflow

- Logi: `logging` ze stdlib. `print` tylko dla komunikatów CLI dla użytkownika.
- Ślady pojedynczych pytań (MLflow Tracing) i eksperymenty (MLflow Tracking) — jedno narzędzie,
  lokalnie w compose, porównania przebiegów jako materiał do pracy.
- MLflow tylko w jednym module (`rag/observability/`); bez niego wszystko działa, testy go nie potrzebują.
- Wyniki eksperymentów także w `results/` (JSON w gicie) — źródło prawdy dla pracy.
- Odrzucone: Prometheus/Grafana/Langfuse — przesada przy jednym użytkowniku i jednej maszynie.

## 2026-11 — Bez porównania z modelami chmurowymi

Lokalność to założenie projektu. Porównujemy lokalne modele różnej wielkości; model chmurowy jako
punkt odniesienia — tylko jeśli promotor o to poprosi.

## 2026-11 — Cały kod w `src/`, podzielony według roli

- `src/extraction/` — skrypt R (ekstrakcja), `src/rag/` — pakiet Pythona z podpakietami:
  `ingestion/` (dokumentacja → indeks), `retrieval/` (zapytanie → chunki), `services/`
  (klienci Ollamy i Qdranta — jedyne miejsce z I/O sieciowym), `evaluation/` (metryki).
- Instalacja przez uv (`uv_build`), komenda `uv run rag`. Układ `src/` gwarantuje, że testy
  działają na zainstalowanym pakiecie, a nie przypadkiem na plikach z katalogu roboczego.
- Oddzielenie `services/` od logiki pozwala testować wszystko bez Dockera (fakes) i podmieniać
  usługi (np. inny magazyn wektorów) bez ruszania reszty.

## 2026-11 — CPU/GPU jako dwie komendy: `make up` i `make up-gpu`

Wcześniej Makefile wykrywał GPU, uruchamiając próbny kontener — działało, ale było nieczytelne.
Teraz wybór jest jawny: `up-gpu` dokłada `docker-compose.gpu.yml` (rezerwacja GPU NVIDIA dla Ollamy).
Plik GPU jest osobny, bo na maszynie bez NVIDIA ta rezerwacja wywraca `docker compose up`.
`scripts/smoke.sh` (parsowanie JSON w awk) zastąpione `rag check` w Pythonie.

## 2026-10 — Zależności tylko, gdy wnoszą coś realnego

HTTP do Ollamy i Qdranta przez `urllib` (`rag/services/http.py`), bez `httpx`/`requests`/`qdrant-client`.
Używamy kilku prostych endpointów JSON, więc biblioteka byłaby tylko nakładką: własny cienki
klient to ~30 linii, łatwo go podmienić w testach (`FakeServices`). Biblioteki, które dają realną
funkcjonalność (np. BM25, reranker, framework pod HTTP API), dodajemy bez oporów, z notką tutaj.

## 2026-10 — Lokalne modele przez Ollamę: qwen3:1.7b + nomic-embed-text

- LLM `qwen3:1.7b` (~1.4 GB): działa obok modelu embeddingów na GPU 6 GB i na CPU.
  Większe modele (4b, 8b) do porównania w M4. `think: false`, bo „myślenie” Qwen3 jest wielokrotnie wolniejsze.
- Embeddingi `nomic-embed-text` (768 wym.) z prefiksami `search_document:` / `search_query:`,
  na których model był trenowany.

## 2026-10 — Qdrant przez REST

Qdrant w Dockerze, kolekcja `r_docs`, odległość kosinusowa, indeks na polu `package` (filtrowanie
po pakiecie). Re-indeksowanie pakietu najpierw liczy embeddingi, potem usuwa stare punkty
i zapisuje nowe — błąd embeddingu nie psuje istniejącego indeksu. Id chunków to UUID5
z `pakiet/temat/numer`, więc są stabilne.

## 2026-10 — Chunking stron pomocy

- Źródło: tekst renderowany przez R (`tools::Rd2txt`), dzielony na sekcje.
- Każdy chunk zaczyna się nagłówkiem `pakiet::temat - tytuł` (+ aliasy), żeby był zrozumiały sam.
- Sekcje pakowane do ~1500 znaków; `Examples` w osobnych chunkach (kod odpowiada na inne pytania
  niż proza); sekcje autorów pomijane; tematy `internal` pomijane przy ekstrakcji.

## 2026-10 — Ewaluacja retrievalu: hit@k i MRR

Pytanie ma listę aliasów stron, które na nie odpowiadają; trafienie = chunk z tematu o takim aliasie.
Rangi liczone po chunkach (tym, co faktycznie trafi do promptu), nie po unikalnych tematach.
