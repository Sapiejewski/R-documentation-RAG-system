"""Retrieval metrics (hit@k, MRR), the evaluation loop on in-memory stores, the question sets, logging."""

import contextlib
import io
import unittest
from pathlib import Path

from rag.evaluation.retrieval import (
    Case,
    CaseResult,
    EvalReport,
    evaluate,
    load_cases,
    rank_of_first_relevant,
)
from rag.ingestion.indexing import Indexer
from rag.ingestion.registry import MemoryRegistry
from rag.retrieval.vector_store import Hit, MemoryStore
from tests.fakes import FakeEmbedder
from tests.fixtures import sync_package

REPO = Path(__file__).resolve().parents[2]


def hit(topic: str, *aliases: str) -> Hit:
    return Hit(topic, 1.0, {"topic": topic, "aliases": list(aliases)})


class RankingTest(unittest.TestCase):
    def test_rank_is_one_based_and_matches_aliases(self):
        hits = [hit("a", "a"), hit("b", "b", "b_all"), hit("c", "c")]
        self.assertEqual(rank_of_first_relevant(hits, ("b_all",)), 2)
        self.assertEqual(rank_of_first_relevant(hits, ("a",)), 1)

    def test_no_match_gives_none(self):
        self.assertIsNone(rank_of_first_relevant([hit("a", "a")], ("z",)))

    def test_report_metrics(self):
        case = Case("q", ("x",))
        report = EvalReport(
            (
                CaseResult(case, 1, ()),
                CaseResult(case, 4, ()),
                CaseResult(case, None, ()),
                CaseResult(case, 2, ()),
            )
        )
        self.assertEqual(report.hit_at(1), 0.25)
        self.assertEqual(report.hit_at(3), 0.5)
        self.assertEqual(report.hit_at(5), 0.75)
        self.assertAlmostEqual(report.mrr, (1 + 1 / 4 + 0 + 1 / 2) / 4)

    def test_empty_report_does_not_divide_by_zero(self):
        self.assertEqual(EvalReport(()).hit_at(5), 0.0)
        self.assertEqual(EvalReport(()).mrr, 0.0)


class EvaluateTest(unittest.TestCase):
    def test_evaluate_on_fixture_package(self):
        embedder, store = FakeEmbedder(), MemoryStore()
        sync_package(Indexer(store=store, registry=MemoryRegistry(), embedder=embedder))
        cases = [
            Case("pad a string to a fixed width", ("str_pad",)),
            Case("remove whitespace from both ends", ("str_trim", "str_squish")),
            Case("quantum chromodynamics", ("str_detect",)),
        ]
        report = evaluate(cases, embedder=embedder, store=store, package="stringr", k=10)
        self.assertEqual(report.results[0].rank, 1)
        self.assertEqual(report.results[1].rank, 1)
        self.assertGreaterEqual(report.hit_at(5), 2 / 3)


class QuestionSetTest(unittest.TestCase):
    def test_stringr_question_set_is_well_formed(self):
        cases = load_cases(REPO / "eval" / "retrieval" / "stringr.json")
        self.assertGreaterEqual(len(cases), 10)
        for case in cases:
            self.assertTrue(case.question.strip())
            self.assertTrue(case.expected)
        self.assertEqual(len({c.question for c in cases}), len(cases))

    def test_missing_question_set_is_reported(self):
        with self.assertRaises(FileNotFoundError):
            load_cases(REPO / "eval" / "retrieval" / "does-not-exist.json")


class LoggingTest(unittest.TestCase):
    def test_indexer_logs_reach_stderr_at_the_configured_level(self):
        from rag.cli import configure_logging

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            configure_logging("INFO")
            sync_package(Indexer(store=MemoryStore(), registry=MemoryRegistry(), embedder=FakeEmbedder()))
        self.assertIn("committed user/stringr 1.5.1", err.getvalue())

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            configure_logging("WARNING")
            sync_package(Indexer(store=MemoryStore(), registry=MemoryRegistry(), embedder=FakeEmbedder()))
        self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
