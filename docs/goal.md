# Cel projektu

**Lokalny asystent dla programistów R oparty na RAG nad dokumentacją R i zainstalowanych pakietów,
zintegrowany z RStudio, wraz z oceną, na ile poprawia on jakość odpowiedzi modeli językowych na
pytania o R.**

Wszystko działa lokalnie (Ollama + Qdrant w Dockerze): bez kosztów API, bez wysyłania kodu
użytkownika na zewnątrz, z powtarzalnymi wynikami. Lokalność to założenie projektu, nie opcja —
porównujemy lokalne modele różnej wielkości, nie modele chmurowe.

**Wyróżnik:** asystent zna dokumentację w **wersjach zainstalowanych u użytkownika** i aktualizuje
się sam — instalacja pakietu na hoście wyzwala reingest, a pakiet jest od razu dostępny w RAG.
Ogólne LLM-y mylą wersje (argumenty dodane/usunięte między wydaniami); ten system nie powinien.

## Pytania badawcze

1. **Wyszukiwanie** — jak skutecznie system odnajduje właściwe strony dokumentacji?
   Metryki: hit@k, MRR na ręcznie przygotowanym zbiorze pytań.
2. **Odpowiedzi** — czy RAG poprawia poprawność odpowiedzi i zmniejsza halucynacje
   (nieistniejące funkcje, argumenty) w porównaniu z samym LLM? Jak zależy to od rozmiaru
   modelu (np. qwen3 1.7b / 4b / 8b)?
   Przewaga dziedziny: kod R da się **wykonać**, więc odpowiedzi można oceniać automatycznie
   (czy kod działa, czy wynik jest poprawny, czy użyte funkcje istnieją).
3. **Użyteczność** — czy integracja z RStudio realnie ułatwia pracę z R?
   Małe badanie z użytkownikami: zadania, czas, skuteczność, opinie.

## Miary zysku

Praca ma pokazywać **widoczny, mierzalny zysk**. Każdy etap roadmapy kończy się jedną z tych liczb:

| Zysk | Miara | Porównanie |
|---|---|---|
| Lepsze wyszukiwanie | hit@k, MRR | warianty retrievalu (chunking, embeddingi, BM25, reranker) |
| Aktualność indeksu | czas od instalacji pakietu do dostępności w RAG; czas synchronizacji | pełny reingest vs przyrostowy |
| Poprawniejsze odpowiedzi | % odpowiedzi, których kod działa i daje dobry wynik | bez RAG vs z RAG |
| Mniej halucynacji | % odpowiedzi z nieistniejącą funkcją/argumentem | bez RAG vs z RAG |
| Tańszy sprzęt | jakość małego modelu z RAG vs dużego bez RAG | qwen3 1.7b / 4b / 8b |
| Szybkość i zasoby | czas odpowiedzi, tokeny/s, pamięć (RAM/VRAM) | CPU vs GPU, rozmiary modeli |
| Ułatwienie pracy | czas i skuteczność rozwiązania zadania | z asystentem vs bez |

Najmocniejszy możliwy wynik: *mały, lokalny model z RAG odpowiada na pytania o R co najmniej tak
dobrze jak kilkukrotnie większy model bez RAG* — czyli ten sam efekt na zwykłym laptopie.

## Zakres

- W zakresie: dokumentacja base R, pakietów recommended, wybranych popularnych pakietów
  (tidyverse, data.table, …) oraz pakietów zainstalowanych u użytkownika.
- Poza zakresem (na razie): vignette, StackOverflow, książki; trenowanie/fine-tuning modeli.

## Rezultaty

- Działający system (CLI + HTTP API + addin RStudio); na hoście potrzebny tylko R, reszta w Dockerze.
- Zbiory ewaluacyjne (retrieval i odpowiedzi) z wynikami eksperymentów w `results/`.
- Tekst pracy (osobno, później).
