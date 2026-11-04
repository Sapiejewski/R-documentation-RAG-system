# Dziennik decyzji

Krótko: co, dlaczego, jakie alternatywy. Najnowsze na górze. Przyda się przy pisaniu
rozdziału o implementacji.

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
  Większe modele (4b, 8b) do porównania w M3. `think: false`, bo „myślenie” Qwen3 jest wielokrotnie wolniejsze.
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
