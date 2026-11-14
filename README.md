# R documentation RAG

Lokalny asystent dla programistów R: wyszukuje w dokumentacji R i pakietów (RAG) i odpowiada
na pytania z użyciem lokalnego modelu językowego. Projekt pracy magisterskiej — cel w [docs/goal.md](docs/goal.md).

## Wymagania

- R ≥ 4.1 i Docker z Compose — `init` sprawdza oba i pomaga doinstalować brakujące rzeczy.
  Bez R: tryb docker. Szczegóły dla Linuxa, macOS i Windowsa: [docs/setup.md](docs/setup.md).
- Do developmentu (testy, CLI `rag`): [uv](https://docs.astral.sh/uv/) (Python 3.14 instaluje się sam).

## Start

```bash
make init                # Windows: .\init.ps1 — sprawdza wymagania, pyta o biblioteki R, uruchamia usługi
make sync                # indeksuje nowe i zmienione pakiety wybranych bibliotek
make doctor              # gdy coś nie działa: co jest nie tak i co zrobić
make search q="pad a string with zeros"
uv run rag ask "What does dplyr's reframe() do?"            # odpowiedź z dokumentacji, z przypisami
uv run rag ask "What does dplyr's reframe() do?" --no-rag   # ten sam model bez dokumentacji
make evaluate PKG=stringr
make logs                # log API; endpointy: http://localhost:8000/docs
```

`make help` pokazuje wszystkie cele. Każdy to jedna, dwie zwykłe komendy — można je uruchamiać ręcznie
(na Windowsie bez `make`: [docs/setup.md](docs/setup.md)).

## Rozwój

```bash
make test       # unit + integration + contract, Python i R (Docker: testowy Qdrant, kontener R)
make test-unit  # tylko szybkie testy logiki, bez Dockera
make test-e2e   # cały stos: R -> API -> Ollama -> Qdrant (po make up; ok. 30 s)
make lint     # ruff
make format   # automatyczne poprawki
```

Dokumentacja: [instalacja na każdym systemie](docs/setup.md), [roadmapa](docs/roadmap.md), [architektura](docs/architecture.md), [decyzje](docs/decisions.md), [infrastruktura](docs/infrastructure.md).
