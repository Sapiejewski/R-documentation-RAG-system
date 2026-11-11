# R documentation RAG

Lokalny asystent dla programistów R: wyszukuje w dokumentacji R i pakietów (RAG) i odpowiada
na pytania z użyciem lokalnego modelu językowego. Projekt magisterski — cel w [docs/goal.md](docs/goal.md).

## Wymagania

- [uv](https://docs.astral.sh/uv/) (Python 3.14 instaluje się sam)
- Docker z Compose

## Start

```bash
cp .env.example .env     # opcjonalnie: modele, porty
make up                  # Qdrant + Ollama na CPU (z kartą NVIDIA: make up-gpu)
make check               # czy wszystko działa
make sync                # zindeksowanie bibliotek R z .env (M1, w budowie)
make search q="pad a string with zeros"
make evaluate PKG=stringr
```

`make help` pokazuje wszystkie cele. Każdy to jedna, dwie zwykłe komendy — można je uruchamiać ręcznie.

## Rozwój

```bash
make test     # testy; część startuje testowego Qdranta w Dockerze (bez Dockera: pomijane)
make lint     # ruff
make format   # automatyczne poprawki
```

Dokumentacja: [roadmapa](docs/roadmap.md), [architektura](docs/architecture.md), [decyzje](docs/decisions.md), [infrastruktura](docs/infrastructure.md).
