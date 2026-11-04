# Roadmapa

Żywy dokument: kolejność i zakres zmieniają się, gdy pojawi się lepszy pomysł albo wyniki
pokażą coś nieoczekiwanego. Bez dat — liczy się kolejność.

Zasady:
- **Najpierw mierz, potem ulepszaj.** Ulepszenia (M4) wynikają z wyników ewaluacji (M3), nie z przeczucia.
- **Każdy etap kończy się liczbą**, którą da się pokazać na obronie (patrz „Zysk”). Miary: [goal.md](goal.md#miary-zysku).
- Jedno zadanie = jedna sesja z Claude = jedna gałąź/commit.

## M0 — Fundamenty ✅

- [x] Pipeline: ekstrakcja R → chunking → embeddingi → Qdrant → wyszukiwanie
- [x] Ewaluacja retrievalu (hit@k, MRR)
- [x] Struktura `src/` z podpakietami, prosty Makefile (CPU/GPU), `rag check`, pytest, ruff, CLAUDE.md, docs

**Zysk:** baseline retrievalu na stringr — 16 pytań, hit@1 94%, MRR 0.938.

## M1 — Pełny korpus i wiarygodny baseline

- [ ] Ekstrakcja wielu pakietów naraz (lista w pliku) + base R i pakiety recommended
- [ ] Tryb „pakiety zainstalowane u użytkownika”
- [ ] Zbiór pytań retrievalu: 100+ pytań z kilku pakietów (także pytania „między pakietami”)
- [ ] Zapis wyników ewaluacji do `results/` (JSON: konfiguracja + metryki), żeby porównywać przebiegi

**Zysk:** wiarygodny baseline na realistycznym korpusie (16 pytań z jednego pakietu to za mało,
a 94% na nim jest zbyt optymistyczne). Plus koszty: czas indeksowania, rozmiar indeksu.

## M2 — Generacja odpowiedzi

- [ ] Podpakiet `rag/generation/`: prompt z kontekstem i cytowaniem źródeł (`pkg::topic`)
- [ ] `rag ask "pytanie"` w CLI
- [ ] HTTP API (pod addin RStudio)

**Zysk:** działający asystent; czas odpowiedzi (retrieval + generacja) na CPU i GPU.

## M3 — Ewaluacja odpowiedzi — główne wyniki pracy

- [ ] Zbiór zadań z wykonywalnym kodem R i oczekiwanym wynikiem (`eval/answers/`)
- [ ] Uruchamianie kodu z odpowiedzi w kontenerze R i sprawdzanie wyniku
- [ ] Wykrywanie halucynacji: czy użyte funkcje/argumenty istnieją w indeksie
- [ ] Porównanie: bez RAG vs z RAG × kilka rozmiarów modelu

**Zysk:** o ile RAG zwiększa odsetek poprawnych odpowiedzi i zmniejsza halucynacje, oraz
czy **mały model z RAG dorównuje dużemu bez RAG** (tańszy sprzęt, mniej pamięci, szybciej).

## M4 — Optymalizacja retrievalu

- [ ] Wybrane na podstawie M3: hybryda z BM25, reranker, inny chunking, inne embeddingi
- [ ] Każde ulepszenie jako eksperyment „przed/po” w `results/`

**Zysk:** przyrost hit@k / poprawności odpowiedzi na ulepszenie, z kosztem (czas, pamięć).

## M5 — Addin RStudio

- [ ] Pakiet R (`src/rstudio_addin/`): pytanie o zaznaczony kod lub ostatni błąd
- [ ] Odpowiedź w panelu (Shiny gadget) ze źródłami

**Zysk:** demo na obronę; asystent tam, gdzie programista R faktycznie pracuje.

## M6 — Badanie użyteczności

- [ ] Scenariusz zadań, kilku uczestników, z asystentem i bez
- [ ] Zamrożenie wyników

**Zysk:** czas rozwiązania zadania i odsetek rozwiązanych zadań z asystentem vs bez.

## M7 — Pisanie

## Pomysły (do rozważenia, poza planem)

Tu trafiają pomysły, które pojawią się po drodze; przenosimy je do etapu, gdy mają sens.
