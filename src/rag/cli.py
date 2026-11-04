"""Command line interface:  python -m rag <command> ..."""

import argparse
import statistics
import sys
import time
from pathlib import Path

from rag.config import Settings
from rag.evaluation.retrieval import evaluate, load_cases
from rag.ingestion.indexing import build_chunks, extracted_path, index_package, read_records
from rag.retrieval.search import format_hit, search
from rag.services.http import ServiceError
from rag.services.ollama import OllamaEmbedder, OllamaLLM
from rag.services.qdrant import QdrantStore


def _embedder(settings: Settings) -> OllamaEmbedder:
    return OllamaEmbedder(
        settings.ollama_url,
        settings.embedding_model,
        doc_prefix=settings.doc_prefix,
        query_prefix=settings.query_prefix,
    )


def _store(settings: Settings) -> QdrantStore:
    return QdrantStore(settings.qdrant_url, settings.collection, settings.qdrant_api_key)


def cmd_index(args, settings: Settings) -> int:
    report = index_package(
        args.package,
        data_dir=settings.data_dir,
        embedder=_embedder(settings),
        store=_store(settings),
        max_chars=args.max_chars,
    )
    print(
        f"Indexed {report.package}: {report.topics} topics -> {report.chunks} chunks "
        f"in collection '{settings.collection}' ({report.seconds:.1f}s)."
    )
    if report.duplicate_topics:
        print(f"Skipped {report.duplicate_topics} duplicate topic names.")
    return 0


def cmd_search(args, settings: Settings) -> int:
    hits = search(args.query, embedder=_embedder(settings), store=_store(settings), k=args.k, package=args.package)
    if not hits:
        print("No results. Has anything been indexed? Try: make ingest")
        return 1
    for rank, hit in enumerate(hits, start=1):
        print(format_hit(rank, hit))
    return 0


def cmd_evaluate(args, settings: Settings) -> int:
    cases_path = Path(args.cases) if args.cases else Path("eval") / "retrieval" / f"{args.package}.json"
    cases = load_cases(cases_path)
    report = evaluate(cases, embedder=_embedder(settings), store=_store(settings), package=args.package, k=args.k)
    for result in report.results:
        rank = f"#{result.rank}" if result.rank else "miss"
        print(f"{rank:>5}  {result.case.question}")
        print(f"       expected: {', '.join(result.case.expected)}")
        print(f"       got:      {', '.join(result.top_topics)}")
    print()
    print(
        f"{len(cases)} questions | hit@1 {report.hit_at(1):.0%} | hit@3 {report.hit_at(3):.0%} | "
        f"hit@5 {report.hit_at(5):.0%} | MRR {report.mrr:.3f}"
    )
    if report.hit_at(5) < args.min_hit5:
        print(f"hit@5 is below the required {args.min_hit5:.0%}.")
        return 1
    return 0


def cmd_inspect(args, settings: Settings) -> int:
    """Show how a package is chunked. Needs only the extracted file, no services."""
    records = read_records(extracted_path(settings.data_dir, args.package))
    chunks, duplicates = build_chunks(records, args.max_chars)
    if args.topic:
        chunks = [c for c in chunks if args.topic == c.topic or args.topic in c.aliases]
        if not chunks:
            print(f"No topic or alias '{args.topic}' in {args.package}.")
            return 1
        for chunk in chunks:
            print(f"{'-' * 72}\n{chunk.section} | chunk {chunk.index + 1}/{chunk.count} | {len(chunk.text)} chars")
            print(chunk.text)
        return 0
    sizes = [len(c.text) for c in chunks]
    print(f"{args.package}: {len(records)} records -> {len(chunks)} chunks ({duplicates} duplicate topics skipped)")
    print(f"chunk size: min {min(sizes)}, median {int(statistics.median(sizes))}, max {max(sizes)} chars")
    topics = list(dict.fromkeys(c.topic for c in chunks))
    print(f"topics ({len(topics)}): {', '.join(topics[:15])}{' ...' if len(topics) > 15 else ''}")
    print(f"See one in full:  python -m rag inspect {args.package} --topic {topics[0]}")
    return 0


def cmd_stats(args, settings: Settings) -> int:
    store = _store(settings)
    print(f"collection '{settings.collection}': {store.count()} chunks")
    if args.package:
        print(f"package '{args.package}': {store.count(args.package)} chunks")
    return 0


def cmd_check(args, settings: Settings) -> int:
    """One real embedding, one real generation and a look at Qdrant: does the stack work, and how fast?"""
    print(f"Ollama at {settings.ollama_url}, Qdrant at {settings.qdrant_url}")
    print("(the first request after startup also loads the model from disk, which is the slow part)")

    started = time.perf_counter()
    vector = _embedder(settings).embed_query("What does lm() return?")
    print(f"embedding   {settings.embedding_model:<20} OK  dim={len(vector)}  {time.perf_counter() - started:.1f}s")

    started = time.perf_counter()
    answer = OllamaLLM(settings.ollama_url, settings.llm_model).generate(
        "In one sentence, what does the R function lm() do?"
    )
    print(
        f"generation  {settings.llm_model:<20} OK  {answer.tokens} tokens at {answer.tokens_per_second:.0f} tok/s"
        f"  {time.perf_counter() - started:.1f}s"
    )
    print(f"            {answer.text[:300]}")

    store = _store(settings)
    stored = f"{store.count()} chunks" if store.exists() else "collection not created yet (run: make ingest)"
    print(f"qdrant      {settings.collection:<20} OK  {stored}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m rag", description="RAG over R package documentation.")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("index", help="chunk, embed and store an extracted package")
    p.add_argument("package")
    p.add_argument("--max-chars", type=int, default=1500)
    p.set_defaults(run=cmd_index)

    p = commands.add_parser("search", help="retrieve the chunks closest to a question")
    p.add_argument("query")
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--package", help="restrict to one package")
    p.set_defaults(run=cmd_search)

    p = commands.add_parser("evaluate", help="measure retrieval quality on a question set")
    p.add_argument("package")
    p.add_argument("--cases", help="JSON question set (default: eval/retrieval/<package>.json)")
    p.add_argument("-k", type=int, default=10)
    p.add_argument("--min-hit5", type=float, default=0.0, help="exit 1 if hit@5 is below this (0-1)")
    p.set_defaults(run=cmd_evaluate)

    p = commands.add_parser("inspect", help="show how an extracted package is chunked (no services needed)")
    p.add_argument("package")
    p.add_argument("--topic", help="print the chunks of this topic or alias")
    p.add_argument("--max-chars", type=int, default=1500)
    p.set_defaults(run=cmd_inspect)

    p = commands.add_parser("stats", help="count what is stored in Qdrant")
    p.add_argument("--package")
    p.set_defaults(run=cmd_stats)

    p = commands.add_parser("check", help="check that Ollama and Qdrant answer, and how fast")
    p.set_defaults(run=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.run(args, Settings.from_env())
    except (ServiceError, FileNotFoundError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
