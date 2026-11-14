"""Answering a question with the local LLM, with or without the retrieved documentation (RAG).

The two modes differ only in the prompt, so comparing their answers isolates what the
documentation adds -- the research question of the thesis:

    with RAG   the question + the k closest help-page chunks of the *installed* versions;
               the model is told to answer from them and cite them as [package::topic]
    without    the question alone: what the model knows by itself

No verification of the answer yet (milestone M3).
"""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from rag.retrieval.search import search
from rag.retrieval.vector_store import Hit, VectorStore
from rag.services.ollama import Generation

log = logging.getLogger(__name__)

WITH_RAG = """You are an assistant for R programmers. Answer the question using the R documentation \
below: it is the documentation of the package versions installed on the user's computer, so prefer \
it over what you remember. Cite every piece of documentation you use by its label, e.g. [stats::lm]. If the \
documentation does not answer the question, say so. Show R code where it helps. Be concise.

Documentation:

{context}

Question: {question}
Answer:"""

WITHOUT_RAG = """You are an assistant for R programmers. Answer the question. Show R code where it \
helps. Be concise.

Question: {question}
Answer:"""

NO_DOCUMENTATION = "(No matching documentation was found.)"


class LLM(Protocol):
    def generate(self, prompt: str) -> Generation: ...


@dataclass(frozen=True)
class Answer:
    question: str
    text: str
    used_rag: bool
    sources: tuple[str, ...]  # "package::topic" given to the model, best match first
    retrieval_seconds: float
    generation: Generation


def source_of(hit: Hit) -> str:
    return f"{hit.payload.get('package', '?')}::{hit.payload.get('topic', '?')}"


def build_prompt(question: str, hits: Sequence[Hit] | None) -> str:
    """The prompt for one question. `hits=None`: without RAG; a list (even empty): with RAG."""
    if hits is None:
        return WITHOUT_RAG.format(question=question)
    blocks = [
        f"[{source_of(h)}] ({h.payload.get('package', '?')} {h.payload.get('version', '?')})\n{h.payload.get('text', '')}"
        for h in hits
    ]
    return WITH_RAG.format(context="\n\n".join(blocks) or NO_DOCUMENTATION, question=question)


def answer(
    question: str,
    *,
    llm: LLM,
    embedder,
    store: VectorStore,
    use_rag: bool = True,
    k: int = 5,
    package: str | None = None,
) -> Answer:
    started = time.perf_counter()
    hits = search(question, embedder=embedder, store=store, k=k, package=package) if use_rag else None
    retrieval_seconds = time.perf_counter() - started

    generation = llm.generate(build_prompt(question, hits))
    sources = tuple(dict.fromkeys(source_of(h) for h in hits or []))  # unique, in rank order
    log.info(
        "ask (%s): %d chunks retrieved in %.2fs; %d tokens generated in %.1fs",
        "with RAG" if use_rag else "without RAG", len(hits or []), retrieval_seconds,
        generation.tokens, generation.seconds,
    )  # fmt: skip
    return Answer(question, generation.text, use_rag, sources, retrieval_seconds, generation)
