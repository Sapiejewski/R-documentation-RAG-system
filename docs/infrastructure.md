# Infrastruktura

Wszystko działa lokalnie w Dockerze; Python (uv) działa na hoście i łączy się z usługami
przez porty na `127.0.0.1`.

| Usługa | Obraz | Port | Rola |
|---|---|---|---|
| `qdrant` | `qdrant/qdrant` | 6333 | baza wektorowa (wolumen `qdrant_data`) |
| `ollama` | `ollama/ollama` | 11434 | modele: embeddingi i generacja (wolumen `ollama_data`) |
| `ollama-init` | `ollama/ollama` | — | jednorazowo pobiera modele z `.env` (`make up` / `make up-gpu`) |
| `r-extract` | `src/extraction/Dockerfile` (`rocker/r-ver`) | — | klient R: manifest i strony pomocy bibliotek z `.env` (`make sync`); `make install` instaluje do wolumenu `r_docker_lib` |

## Konfiguracja

`cp .env.example .env` i edycja. Zmienne są opisane w `.env.example`; wymagana jest tylko
`R_USER_LIBRARY` (dla `make sync`). Docker Compose i kod Pythona (`rag/config.py`) czytają `.env`
same — Makefile go nie potrzebuje.

## Biblioteki R (`make sync`)

| Zmienna | Montowana jako | Domyślnie |
|---|---|---|
| `R_SYSTEM_LIBRARY` | `/libraries/system` (tylko odczyt) | `/usr/lib/R/library` (base R na Debianie/Ubuntu) |
| `R_USER_LIBRARY` | `/libraries/user` (tylko odczyt) | brak — w R: `Sys.getenv("R_LIBS_USER")` |
| — | `/libraries/docker` (wolumen `r_docker_lib`) | biblioteka eksperymentów (`make install`) |
| `HOST_UID`, `HOST_GID` | użytkownik kontenera | `1000` — pliki w `data/` należą do ciebie, nie do roota |

Oba foldery muszą istnieć (`create_host_path: false`): zła ścieżka to czytelny błąd zamiast
pustego folderu roota, w którym R nie mógłby potem instalować. Bibliotekę użytkownika R tworzy
przy pierwszym `install.packages()`; można też `mkdir -p` wcześniej.

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
