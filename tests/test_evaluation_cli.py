import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rag.cli import main
from rag.evaluation import (
    Case,
    CaseResult,
    EvalReport,
    evaluate,
    load_cases,
    rank_of_first_relevant,
)
from rag.index import index_package
from rag.stores import Hit, MemoryStore
from tests.fakes import FakeEmbedder
from tests.fixtures import write_extracted

REPO = Path(__file__).resolve().parent.parent


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
        with tempfile.TemporaryDirectory() as tmp:
            write_extracted(Path(tmp))
            embedder, store = FakeEmbedder(), MemoryStore()
            index_package(
                "stringr",
                data_dir=Path(tmp),
                embedder=embedder,
                store=store,
                log=lambda _: None,
            )
        cases = [
            Case("pad a string to a fixed width", ("str_pad",)),
            Case("remove whitespace from both ends", ("str_trim", "str_squish")),
            Case("quantum chromodynamics", ("str_detect",)),
        ]
        report = evaluate(
            cases, embedder=embedder, store=store, package="stringr", k=10
        )
        self.assertEqual(report.results[0].rank, 1)
        self.assertEqual(report.results[1].rank, 1)
        self.assertGreaterEqual(report.hit_at(5), 2 / 3)


class QuestionSetTest(unittest.TestCase):
    def test_stringr_question_set_is_well_formed(self):
        cases = load_cases(REPO / "eval" / "stringr.json")
        self.assertGreaterEqual(len(cases), 10)
        for case in cases:
            self.assertTrue(case.question.strip())
            self.assertTrue(case.expected)
        self.assertEqual(len({c.question for c in cases}), len(cases))

    def test_missing_question_set_is_reported(self):
        with self.assertRaises(FileNotFoundError):
            load_cases(REPO / "eval" / "does-not-exist.json")


class CliTest(unittest.TestCase):
    def run_cli(self, *argv: str, data_dir: Path) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.dict(os.environ, {"RAG_DATA_DIR": str(data_dir)}),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_inspect_summary_and_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_extracted(Path(tmp))
            code, out, _ = self.run_cli("inspect", "stringr", data_dir=Path(tmp))
            self.assertEqual(code, 0)
            self.assertIn("str_pad", out)
            self.assertIn("chunk size:", out)

            code, out, _ = self.run_cli(
                "inspect", "stringr", "--topic", "str_squish", data_dir=Path(tmp)
            )
            self.assertEqual(code, 0)
            self.assertIn("stringr::str_trim", out)  # found through its alias

            code, out, _ = self.run_cli(
                "inspect", "stringr", "--topic", "nope", data_dir=Path(tmp)
            )
            self.assertEqual(code, 1)

    def test_missing_package_is_a_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = self.run_cli("inspect", "ghost", data_dir=Path(tmp))
            self.assertEqual(code, 1)
            self.assertIn("make extract PKG=ghost", err)

    def test_unreachable_services_are_a_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_extracted(Path(tmp))
            env = {
                "OLLAMA_URL": "http://127.0.0.1:9",
                "QDRANT_URL": "http://127.0.0.1:9",
            }
            with mock.patch.dict(os.environ, env):
                code, _, err = self.run_cli("index", "stringr", data_dir=Path(tmp))
            self.assertEqual(code, 1)
            self.assertIn("make up", err)


if __name__ == "__main__":
    unittest.main()
