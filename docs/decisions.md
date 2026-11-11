# Dziennik decyzji

Krótko: co, dlaczego, jakie alternatywy. Najnowsze na górze. Przyda się przy pisaniu
rozdziału o implementacji.

## 2026-11 — Klient R na hoście, `init` / `doctor`, dwa tryby

Problem: biblioteki R hosta były podłączane do kontenera bind mountem. Folder musiał istnieć
(biblioteka osobista powstaje dopiero przy pierwszym `install.packages()`), a zestaw folderów był
sztywny — nie da się wskazać dowolnego folderu (addin, `renv`) bez zmiany `docker-compose.yml`.

- **Klient R działa na hoście** (część M2 przesunięta do M1): R użytkownika widzi każdy folder,
  `.libPaths()` podaje tylko istniejące biblioteki. Kontenery nie montują folderów hosta.
- **Biblioteka = jej ścieżka** (bezwzględna, z `/`). Wybór: `init` pyta, zapis `RDOCS_LIBRARIES`
  (separator jak w `R_LIBS`: `:` / `;` na Windowsie); bez wyboru — `.libPaths()`. Jedno miejsce
  wyboru (`selected_libraries()`) podmieni później addin.
- **`init` i `doctor` to te same kontrole** (`CHECKS` w `src/client/setup.R`): każda zwraca wynik,
  podpowiedź i opcjonalną naprawę. `doctor` raportuje, `init` proponuje naprawy. Nowe wymaganie =
  nowa kontrola + wiersz w tabeli wymagań ([setup.md](setup.md)).
- **Nic bez zgody:** instalacja R, httr2 i start usług tylko po „tak”; bez terminala zawsze „nie”.
- **Bootstrap w dwóch małych skryptach** (`init.sh` dla Linuxa/macOS, `init.ps1` dla Windowsa),
  bo nie ma języka obecnego wszędzie przed instalacją R; robią tylko „czy jest R?”. Reszta w R —
  działa tak samo na każdym systemie i przejdzie wprost do pakietu R (M2) i addina (M6).
  Odrzucone: Python (sprzeczny z „na hoście tylko R”), jeden skrypt sh (brak na Windowsie).
- **`GET /health` raportuje zależności** (Qdrant, Ollama, modele), żeby każdy klient — `doctor`,
  addin, `curl` — widział to samo. Zawsze 200, gdy API działa (healthcheck Dockera), `degraded` z przyczyną.
- **Tryb docker** (`make sync-docker`): ten sam klient w kontenerze, tylko biblioteka Dockera
  z datowanego snapshotu CRAN. Dla osób bez R i jako **stały korpus do ewaluacji** — wyniki
  powtarzalne na każdej maszynie, niezależne od tego, co ktoś ma zainstalowane.
- Folder `src/extraction` → `src/client`: to już cały klient R hosta, nie tylko ekstrakcja.
- Konfiguracja na razie w `.env` projektu; w M2 przejdzie do `tools::R_user_dir("rdocs", "config")`.

## 2026-11 — Testy według poziomów: unit → integration → contract → e2e

- Katalog na poziom (`tests/unit`, `integration`, `contract`, `e2e`), Python i R razem
  (`tests/<poziom>/r/` dla testthat) — poziom testu widać po ścieżce, nie po języku.
  Każdy katalog ma `__init__.py` z opisem: co pokrywa i czego potrzebuje.
- Kontrakt R ↔ Python: wspólne przykłady żądań (`tests/contract/examples/*.json`). Python sprawdza,
  że API je przyjmuje; R — że klient wysyła żądania o tym samym kształcie (te same pola na każdym
  poziomie). Rozjazd po jednej stronie psuje test, a nie synchronizację u użytkownika.
- e2e na prawdziwym stosie, ale na własnym kontenerze API i jednorazowej kolekcji: test nie rusza
  indeksu użytkownika. Poza `make test` (wymaga `make up`, trwa ok. 30 s).
- Testy R w osobnej usłudze `r-test` (ten sam obraz co `r-extract`), która montuje tylko kod
  i testy: nie potrzebuje bibliotek z `.env` ani działających usług.

## 2026-11 — Klient R przez HTTP (`src/extraction/`)

- Dwa pliki według roli: `extract.R` czyta zainstalowane pakiety (bez sieci), `api.R` prowadzi
  rozmowę z API. Klient nie podejmuje decyzji: wysyła manifest i robi to, o co prosi plan.
- `api_post()` to jedyne miejsce z httr2: JSON, do 3 prób przy 503 (bezpieczne, bo API jest
  idempotentne), a przy błędzie treść odpowiedzi serwisu (np. które pole jest złe).
- Błąd jednego pakietu: komunikat i przejście do następnego; bez `commit` stara wersja zostaje
  aktywna, a następny sync poprosi o pakiet ponownie. `make sync` kończy się błędem, gdy coś zawiodło.
- Testy `testthat` z `httr2::local_mocked_responses`: fałszywe API nagrywa żądania, testy sprawdzają
  kolejność rozmowy, rozmiar paczek, pola zgodne ze schematem `HelpPage`. Bez Dockera z usługami
  i bez Pythona. Zgodność z prawdziwym API: kontrakt i e2e (zob. wpis o poziomach testów).
- Pliki `data/extracted/` znikają: nic nie jest zapisywane na dysk po drodze.

## 2026-11 — HTTP API synchronizacji (`rag/api/`)

- Endpointy odpowiadają krokom `Indexer`: `POST /sync`, `/packages/begin`, `/packages/pages`,
  `/packages/commit`, plus `GET /health` (zwraca też `index_format` — klient widzi, że zmiana
  modelu wymusi pełne przeindeksowanie). Ciało żądania to modele z `rag/schemas.py`; każdy
  krok pakietu niesie całą `installation`, więc serwer nie trzyma stanu sesji między żądaniami.
- Handlery to zwykłe `def`: indeksowanie blokuje na HTTP do Ollamy/Qdranta, FastAPI uruchamia je
  w wątkach. Odpowiedź dopiero po zapisie = backpressure bez kolejki zadań.
- Błędy: 422 z nazwą pola (walidacja pydantic, `extra="forbid"` łapie literówki klienta),
  503 gdy Ollama/Qdrant nie działa (klient może ponowić — paczki są idempotentne),
  limit 500 stron na żądanie.
- Logowanie: middleware loguje każde żądanie (metoda, ścieżka, status, czas); `/health` tylko na
  DEBUG, bo healthcheck odpytuje co 5 s. Szczegóły pracy (plan, commit, paczki) loguje `Indexer`.
- Uruchamianie: `rag serve` (uvicorn), w Dockerze usługa `rag` z `Dockerfile` w katalogu głównym
  (kontekst budowania musi obejmować `pyproject.toml` i `uv.lock`).
- Zależności: **FastAPI** + **uvicorn** (standard; walidacja i `/docs` za darmo), w testach
  `TestClient` z **httpx2** (zalecany przez Starlette następca `httpx`).
- Odrzucone: serwer na `http.server` ze standardowej biblioteki — walidacja, kody błędów
  i dokumentacja API do napisania ręcznie, czyli dokładnie to, co FastAPI robi dobrze.

## 2026-11 — Zależności: standard rynkowy albo realny zysk (zastępuje wpis z 2026-10)

Zewnętrzną bibliotekę bierzemy, gdy jest **standardem rynkowym** albo **znacząco ułatwia zadanie
lub poprawia wydajność** (pydantic, FastAPI, ORM, numpy, BM25…). Nie odtwarzamy ręcznie tego, co
dojrzała biblioteka robi dobrze — kod ma być zrozumiały dla innych, a standard jest zrozumiały
z definicji. Unikamy tylko cienkich nakładek bez wartości dodanej: klienci HTTP do Ollamy i Qdranta
zostają na `urllib` (kilka endpointów JSON, łatwa podmiana w testach).

## 2026-11 — Indeksowanie przyrostowe: generacje, aktywacja przy `commit`

- Każda wersja pakietu to osobna *generacja* punktów (`generation` = hash z `built` + `index_format`;
  id punktu z biblioteki, generacji i klucza chunka). Nowa generacja jest zapisywana jako `active: false`.
- `commit`: najpierw aktywacja nowej generacji, potem usunięcie starej — wyszukiwanie widzi przez chwilę
  obie, nigdy żadnej. Wyszukiwanie filtruje `active: true`, więc nie miesza dwóch wersji.
- Przerwany transfer: stara generacja zostaje aktywna, rejestr wciąż ją wskazuje, więc następny `plan`
  poprosi o pakiet ponownie; `begin` usuwa nieaktywne resztki. Ponowiona paczka niczego nie psuje
  (te same id, wektory z hashy).
- Odrzucone: aktualizacja „w miejscu” (te same id dla nowej wersji) — w trakcie transferu i po przerwaniu
  indeks mieszałby strony dwóch wersji.
- Indeksy pól w Qdrancie tylko dla filtrowanych pól (`library`, `package`, `generation`, `content_hash`,
  `aliases`, `active`): każdy kosztuje ok. 0,5 s przy tworzeniu kolekcji. `wait=false` nie pomaga —
  przenosi koszt na pierwszy zapis (zmierzone: 4 s).

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
- **Poziom chunka:** `content_hash = sha256(tożsamość embeddera + tekst)` w payloadzie (tożsamość =
  model + prefiks dokumentu: wszystko, od czego zależy wektor). Przed embeddingiem szukamy w Qdrancie
  punktu o tym samym hashu i kopiujemy jego wektor — embedding tylko dla nowych tekstów.
- **Wersja chunkera nie należy do hasha**, tylko do rejestru (`index_format` = wersja chunkera +
  tożsamość embeddera + `max_chars`). Wektor zależy wyłącznie od tekstu i modelu; ale po zmianie
  chunkera niezmieniona instalacja nie zostałaby wysłana — dlatego zmiana `index_format` wymusza
  ponowne wysłanie pakietu, a hashe sprawiają, że embedding obejmie tylko chunki o zmienionym tekście.
- **Stan indeksu w Qdrancie**, nie w pliku: osobna kolekcja bez wektorów `<kolekcja>_packages`, jeden
  punkt na (biblioteka, pakiet) z instalacją i `index_format` — jedno źródło prawdy, nie rozjedzie
  się z indeksem. (Qdrant obsługuje kolekcje bez wektorów — sprawdzone na v1.19.1.)
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

## 2026-10 — Zależności tylko, gdy wnoszą coś realnego (zastąpione, zob. wyżej)

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
