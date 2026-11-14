"""Answering with and without RAG (rag/generation): what the model is given, what is reported."""

import unittest

from rag.generation.answer import NO_DOCUMENTATION, answer, build_prompt
from rag.ingestion.indexing import Indexer
from rag.ingestion.registry import MemoryRegistry
from rag.retrieval.vector_store import MemoryStore
from rag.services.ollama import Generation
from tests.fakes import FakeEmbedder
from tests.fixtures import sync_package


class RecordingLLM:
    """Answers with a fixed text and keeps every prompt it was given."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> Generation:
        self.prompts.append(prompt)
        return Generation(text="Use str_pad(). [stringr::str_pad]", tokens=8, seconds=0.5)


class AnswerTest(unittest.TestCase):
    def setUp(self):
        self.store, self.embedder, self.llm = MemoryStore(), FakeEmbedder(), RecordingLLM()
        sync_package(Indexer(store=self.store, registry=MemoryRegistry(), embedder=self.embedder))

    def ask(self, question: str, **options):
        return answer(question, llm=self.llm, embedder=self.embedder, store=self.store, **options)

    def test_with_rag_the_model_gets_the_documentation_and_is_asked_to_cite_it(self):
        result = self.ask("pad a string with zeros", k=2)

        prompt = self.llm.prompts[0]
        self.assertIn("[stringr::str_pad] (stringr 1.5.1)", prompt)  # with the installed version
        self.assertIn("Cite every piece of documentation", prompt)
        self.assertTrue(prompt.rstrip().endswith("Question: pad a string with zeros\nAnswer:"))
        self.assertEqual(result.sources[0], "stringr::str_pad")
        self.assertTrue(result.used_rag)

    def test_without_rag_the_model_gets_only_the_question(self):
        result = self.ask("pad a string with zeros", use_rag=False)

        prompt = self.llm.prompts[0]
        self.assertNotIn("Documentation:", prompt)
        self.assertNotIn("stringr::", prompt)
        self.assertEqual(result.sources, ())
        self.assertFalse(result.used_rag)

    def test_both_modes_ask_the_same_question(self):
        self.ask("trim whitespace", use_rag=True)
        self.ask("trim whitespace", use_rag=False)

        self.assertTrue(all(p.rstrip().endswith("Question: trim whitespace\nAnswer:") for p in self.llm.prompts))

    def test_sources_are_unique_in_rank_order(self):
        result = self.ask("str_pad width side pad", k=5)  # several chunks of the same page

        self.assertEqual(len(result.sources), len(set(result.sources)))

    def test_an_empty_index_says_so_instead_of_inventing_context(self):
        self.assertIn(NO_DOCUMENTATION, build_prompt("anything", []))

    def test_the_answer_and_its_cost_are_reported(self):
        result = self.ask("pad a string")

        self.assertEqual(result.text, "Use str_pad(). [stringr::str_pad]")
        self.assertEqual(result.generation.tokens, 8)
        self.assertGreaterEqual(result.retrieval_seconds, 0)


if __name__ == "__main__":
    unittest.main()
