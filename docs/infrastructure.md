# Infrastruktura

Wszystko działa lokalnie w Dockerze; Python (uv) działa na hoście i łączy się z usługami
przez porty na `127.0.0.1`.

| Usługa | Obraz | Port | Rola |
|---|---|---|---|
| `qdrant` | `qdrant/qdrant` | 6333 | baza wektorowa (wolumen `qdrant_data`) |
| `ollama` | `ollama/ollama` | 11434 | modele: embeddingi i generacja (wolumen `ollama_data`) |
| `ollama-init` | `ollama/ollama` | — | jednorazowo pobiera modele z `.env` (`make up` / `make up-gpu`) |
| `r-extract` | `rocker/r-ver` | — | ekstrakcja stron pomocy (`make extract`); pakiety R w wolumenie `r_lib` |

## Konfiguracja

`cp .env.example .env` i edycja. Wszystkie zmienne są opcjonalne i opisane w `.env.example`.
Docker Compose i kod Pythona (`rag/config.py`) czytają `.env` same — Makefile go nie potrzebuje.

## CPU czy GPU

| Komenda | Pliki Compose | Kiedy |
|---|---|---|
| `make up` | `docker-compose.yml` | każdy komputer; Ollama na CPU |
| `make up-gpu` | `docker-compose.yml` + `docker-compose.gpu.yml` | karta NVIDIA; Ollama na GPU |

`docker-compose.gpu.yml` dokłada tylko rezerwację GPU dla usługi `ollama`. Jest osobnym plikiem,
bo na maszynie bez NVIDIA ta rezerwacja powoduje błąd startu. Wymaga NVIDIA Container Toolkit
(Linux) lub Docker Desktop z WSL2 (Windows).

Sprawdzenie, po użyciu modelu: `docker compose exec ollama ollama ps` → `PROCESSOR 100% GPU`.
Dla porządku skali: qwen3:1.7b na CPU ok. 30 tokenów/s, na GTX 1660 Ti ok. 97 tokenów/s.
Przełączenie: `make down`, potem drugie `make up…`.

## Typowe problemy

- `Cannot reach ... Try: make up` — usługi nie działają: `make up`, potem `make check`.
- `Model ... may be missing` — `make up` pobiera modele ponownie.
- `vector size` przy indeksowaniu — zmieniono model embeddingów; usuń kolekcję
  (`curl -X DELETE http://localhost:6333/collections/r_docs`) albo ustaw inną `QDRANT_COLLECTION`.
- `make down` zatrzymuje usługi, dane zostają w wolumenach; `docker compose down -v` usuwa je.
