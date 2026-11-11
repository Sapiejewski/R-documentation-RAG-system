# Instalacja i uruchomienie: przepływ na każdym systemie

Ten dokument mówi, **co użytkownik uruchamia, co dzieje się po kolei i gdzie to jest w kodzie** —
osobno dla Linuxa, macOS i Windowsa. Przy każdej zmianie wymagań albo kroków startowych aktualizuj
go razem z kodem.

## W skrócie

- Na komputerze użytkownika: **R** (zwykle już jest — to programista R) i **Docker**.
  Wszystko inne (Python, Qdrant, Ollama) działa w Dockerze.
- Pierwsze uruchomienie: **`init`** — jedno polecenie, które sprawdza wymagania, proponuje naprawy
  (zawsze pyta), pyta o biblioteki R do indeksowania i uruchamia usługi.
- Diagnostyka w dowolnym momencie: **`doctor`** — te same kontrole, tylko raport + podpowiedzi.
- Indeksowanie: **`sync`** — wysyła do serwisu tylko nowe i zmienione pakiety.

| | Linux / macOS | Windows (PowerShell) |
|---|---|---|
| pierwsze uruchomienie | `make init` | `.\init.ps1` |
| diagnostyka | `make doctor` | `Rscript src/client/main.R doctor` |
| indeksowanie | `make sync` | `Rscript src/client/main.R sync` |
| start / stop usług | `make up` / `make down` | `docker compose up -d --wait --build qdrant ollama rag` / `docker compose down` |

Na Windowsie zwykle nie ma `make`; każdy cel Makefile to jedno, dwa zwykłe polecenia, więc
można je wpisać ręcznie (`make help` / Makefile pokazuje, jakie).

## Dwa tryby klienta R

Klient R (`src/client/`) to jeden kod, uruchamiany na dwa sposoby. Różnią się tylko tym, gdzie
działa R i które biblioteki widzi (`selected_libraries()` w `config.R`).

| Tryb | Gdzie działa R | Jakie biblioteki | Dla kogo |
|---|---|---|---|
| **host** (domyślny) | R użytkownika | wybrane w `init` (`RDOCS_LIBRARIES`), domyślnie `.libPaths()` | programista R — właściwy użytkownik |
| **docker** | kontener `r-extract` | tylko biblioteka Dockera (wolumen `r_docker_lib`, pakiety z `make install`) | ktoś bez R (promotor, recenzent, demo); **stały korpus do ewaluacji** |

Tryb docker nie potrzebuje R na hoście ani żadnych folderów hosta. Jego pakiety pochodzą
z datowanego snapshotu CRAN obrazu `rocker`, więc wyniki ewaluacji są powtarzalne na każdej maszynie.

## Wymagania

Każde wymaganie ma tu wiersz, kontrolę w `doctor` (`CHECKS` w `src/client/setup.R`) i czytelny
błąd w miejscu użycia. Nowe wymaganie = nowy wiersz + nowa kontrola.

| Wymaganie | Tryb | Minimum | Kontrola (`doctor`) | `init` naprawia? | Ręcznie |
|---|---|---|---|---|---|
| R (`Rscript`) | host | 4.1 (wymaga tego httr2) | `R` (a wcześniej `init.sh`/`init.ps1`: czy R w ogóle jest) | instaluje za zgodą: apt/dnf (Linux), brew (macOS), winget (Windows) | <https://cloud.r-project.org> |
| pakiet R `httr2` | host | — | `httr2` | tak, za zgodą: `install.packages("httr2")` do biblioteki osobistej (tworzy ją) | `install.packages("httr2")` w R |
| Docker + Compose v2, uruchomiony | oba | Compose v2 | `Docker` | nie — tylko podpowiedź | Linux: Docker Engine; macOS, Windows: Docker Desktop (uruchomiony!) |
| biblioteki R do indeksowania | host | co najmniej jedna istnieje | `libraries` | pyta i zapisuje w `.env` | `RDOCS_LIBRARIES` w `.env` |
| API `rag` odpowiada | oba | — | `API` | tak, za zgodą: uruchamia usługi | `make up` |
| Qdrant i Ollama gotowe, modele pobrane | oba | — | `services` (z `GET /health`) | tak, za zgodą: uruchamia usługi i pobiera modele | `make up` |

Python i `uv` nie są wymaganiem użytkownika — są potrzebne tylko do developmentu (testy, CLI `rag`).

## Co robi `init`, krok po kroku

Wspólne dla wszystkich systemów od kroku 2: to kod R (`init()` w `src/client/setup.R`).

```
1. bootstrap (init.sh / init.ps1)   czy jest R? nie -> pokaż polecenie instalacji, zapytaj [y/N]
                                     brak zgody -> instrukcja + tryb docker, koniec
2. kontrole R, httr2, Docker         nieudana kontrola z naprawą -> "Fix it now? [Y/n]"
                                     coś nadal nie działa -> komunikat, co zrobić, koniec
3. wybór bibliotek                   lista .libPaths() z liczbą pakietów; numery albo Enter = wszystkie;
                                     potem dowolne inne foldery (np. biblioteka renv projektu)
                                     -> zapis RDOCS_LIBRARIES w .env (bez .env: kopia .env.example)
4. kontrole libraries, API, services API nie odpowiada / brak modeli -> "Fix it now?" -> docker compose up
                                     + pobranie modeli (to samo co make up)
5. koniec                            "Ready. Index your libraries: make sync"
```

Zasady:
- **Nic nie jest instalowane ani uruchamiane bez pytania.** Enter przy pytaniu tak/nie wybiera
  wartość domyślną (pokazaną wielką literą: `[Y/n]`).
- **`init` można uruchomić ponownie** — np. żeby zmienić biblioteki (zapyta „Change them?”).
- **Bez terminala (skrypt, test) nikt nie może odpowiedzieć**: każde „tak/nie” to „nie” — `init`
  niczego wtedy nie instaluje ani nie uruchamia, tylko raportuje; biblioteki: wszystkie z `.libPaths()`.

## Linux

```bash
git clone <repo> && cd R-documentation-RAG-system
make init      # albo: sh init.sh
make sync
```

- Brak R: `init.sh` proponuje `sudo apt-get install -y r-base` (Debian/Ubuntu) albo
  `sudo dnf install -y R` (Fedora). Inna dystrybucja: instrukcja z CRAN.
- Docker: Docker Engine z wtyczką Compose. Jeśli `doctor` mówi „installed, but not running (or no
  permission)”: `sudo systemctl start docker`, a użytkownik musi być w grupie `docker`
  (`sudo usermod -aG docker $USER`, potem ponowne zalogowanie).
- Typowe biblioteki: `/usr/lib/R/library` (base R), `/usr/lib/R/site-library`,
  `~/R/x86_64-pc-linux-gnu-library/<wersja>` (osobista; powstaje przy pierwszej instalacji pakietu).

## macOS

```bash
make init      # albo: sh init.sh
make sync
```

- Brak R: `init.sh` proponuje `brew install --cask r` (jeśli jest Homebrew); bez Homebrew —
  instalator `.pkg` z CRAN.
- Docker: Docker Desktop. **Musi być uruchomiony** (ikona wieloryba) — inaczej `doctor` zgłosi
  „installed, but not running”.
- Typowe biblioteki: `/Library/Frameworks/R.framework/Versions/<wersja>/Resources/library`,
  `~/Library/R/<arch>/<wersja>/library`.

## Windows

W PowerShell, w folderze projektu:

```powershell
.\init.ps1
# jeśli skrypty są zablokowane:
powershell -ExecutionPolicy Bypass -File init.ps1

Rscript src/client/main.R sync
```

- Brak R: `init.ps1` proponuje `winget install --exact --id RProject.R`; bez winget — instalator z CRAN.
- **Instalator R nie dodaje R do PATH.** `init.ps1` sam szuka `Rscript.exe` w `Program Files\R\R-*\bin`
  i `%LOCALAPPDATA%\Programs\R` (najnowsza wersja). Żeby wpisywać `Rscript` ręcznie (sync, doctor),
  dodaj `...\R\R-<wersja>\bin` do PATH albo podaj pełną ścieżkę.
- Docker: Docker Desktop z backendem WSL2, uruchomiony.
- `make` zwykle nie ma — polecenia z tabeli „W skrócie”.
- `RDOCS_LIBRARIES` rozdziela foldery średnikiem (`;`), bo dwukropek jest w `C:/...`.
- Typowe biblioteki: `C:/Program Files/R/R-<wersja>/library`,
  `%LOCALAPPDATA%/R/win-library/<wersja>` (osobista).
- **Status: `init.ps1` nie był jeszcze uruchomiony na Windowsie** (development odbywa się na Linuxie);
  sprawdzenie jest zadaniem w roadmapie (M1).

## Bez R na komputerze: tryb docker

```bash
make up                       # usługi
make install PKG=stringr      # instalacja pakietu do biblioteki Dockera (snapshot CRAN)
make sync-docker              # indeksowanie biblioteki Dockera
```

Windows: `docker compose run --rm --no-deps r-extract install stringr`, potem
`docker compose run --rm r-extract sync`.

## Konfiguracja

Jedno miejsce: `.env` w katalogu projektu (wzorzec z opisem każdej zmiennej: `.env.example`).
Czytają go: Docker Compose, serwis Pythona (`rag/config.py`) i klient R (`load_env_file()` w `config.R`).
Zmienna ustawiona w środowisku ma pierwszeństwo przed `.env`.

| Zmienna | Kto używa | Kto ustawia |
|---|---|---|
| `RDOCS_LIBRARIES` | klient R (tryb host) | `init` (pytanie o biblioteki); ręcznie też można |
| `RAG_HOST_PORT` / `RAG_URL` | klient R: gdzie jest API | domyślnie `http://localhost:8000` |
| modele, porty, `LOG_LEVEL` | usługi w Dockerze | `.env.example` |

Docelowo (M2, pakiet R) ustawienia klienta przejdą do standardowego miejsca R:
`tools::R_user_dir("rdocs", "config")` — wspólnego dla wszystkich systemów i niezależnego od folderu projektu.

## `doctor`: przykład

```
OK    R          4.3.3
FAIL  httr2      not installed
                 -> in R: install.packages("httr2")
OK    Docker     Compose 2.29.7
OK    libraries  RDOCS_LIBRARIES in .env
                 /usr/lib/R/library  (29 packages)
                 /home/ja/R/x86_64-pc-linux-gnu-library/4.3  (12 packages)
FAIL  API        not checked: needs httr2
FAIL  services   not checked: needs httr2

Some checks failed; each says what to do (docs/setup.md).
```

Kod wyjścia 1, gdy coś nie działa — można go użyć w skryptach. `services` pokazuje to, co serwis
raportuje w `GET /health` (stan Qdranta, Ollamy, pobranych modeli) — ten sam raport zobaczy addin.

## Co i gdzie jest testowane

| Element | Test | Gdzie |
|---|---|---|
| kontrole, pytania, naprawy, wybór bibliotek, zapis `.env` | unit (R) | `tests/unit/r/test-setup.R`, `test-config.R` |
| `GET /health` ze stanem usług | contract + integration | `tests/contract/test_api.py`, `tests/integration/test_status.py` |
| sync w trybie docker | e2e | `tests/e2e/test_sync.py` (`DockerModeTest`) |
| sync w trybie host | e2e, pomijany bez httr2 na hoście | `tests/e2e/test_sync.py` (`HostModeTest`) |
| `init.sh` bez R | ręcznie (Linux) | PATH bez `Rscript`: propozycja instalacji, odmowa → instrukcja |
| `init.ps1` | **nieprzetestowany** | do zrobienia na Windowsie (roadmapa) |
| macOS | **nieprzetestowany** | do zrobienia (roadmapa) |

## Rozbudowa

- **Nowe wymaganie:** funkcja kontroli w `CHECKS` (`setup.R`), opcjonalnie `fix`, wiersz w tabeli
  wymagań wyżej, test w `tests/unit/r/test-setup.R`.
- **M2 (pakiet R):** `init()` staje się `rdocs::setup()`, `doctor()` — `rdocs::doctor()`; konfiguracja
  w `tools::R_user_dir()`. Bootstrap (`init.sh`/`init.ps1`) zostaje tylko do sprawdzenia, czy jest R.
- **M6 (addin RStudio):** te same funkcje, ale pytania zadaje okno addina zamiast konsoli
  (podmiana `ask()`), a „Diagnostyka” pokazuje wynik `doctor`.
