import unittest

from rag.chunking import chunk_description, chunk_record, chunk_topic, split_text
from tests.fixtures import RECORDS

STR_PAD = RECORDS[1]
STR_TRIM = RECORDS[2]
STR_DETECT = RECORDS[3]
HEADER = "stringr::str_pad - Pad a string to minimum width"


def long_record(argument_count: int = 40) -> dict:
    items = "\n\n".join(f"  arg_{i}: " + "word " * 25 for i in range(argument_count))
    text = f"f   package:p   R Documentation\n\nTitle\n\nDescription:\n\n     Does things.\n\nArguments:\n\n{items}\n"
    return {"type": "topic", "package": "p", "version": "1", "name": "f", "title": "Title", "aliases": ["f"], "text": text}


class ChunkTopicTest(unittest.TestCase):
    def test_every_chunk_starts_with_the_header(self):
        chunks = chunk_topic(STR_PAD)
        self.assertTrue(chunks)
        for chunk in chunks:
            self.assertTrue(chunk.text.startswith(HEADER), chunk.text[:80])

    def test_examples_are_a_separate_chunk(self):
        chunks = chunk_topic(STR_PAD)
        examples = [c for c in chunks if c.section == "Examples"]
        self.assertEqual(len(examples), 1)
        self.assertIn('str_pad(1:3, 3, pad = "0")', examples[0].text)
        for chunk in chunks:
            if chunk.section != "Examples":
                self.assertNotIn("rbind(", chunk.text)

    def test_prose_sections_are_packed_together_when_small(self):
        chunks = chunk_topic(STR_PAD)
        self.assertEqual(chunks[0].section, "Description, Usage, Arguments, Value, See Also")
        self.assertEqual(len(chunks), 2)

    def test_author_section_is_dropped(self):
        for chunk in chunk_topic(STR_PAD):
            self.assertNotIn("somebody@example.com", chunk.text)

    def test_aliases_in_header_only_when_there_are_several(self):
        self.assertNotIn("Aliases:", chunk_topic(STR_PAD)[0].text)
        self.assertIn("Aliases: str_trim, str_squish", chunk_topic(STR_TRIM)[0].text)

    def test_single_alias_given_as_a_bare_string(self):
        chunks = chunk_topic(STR_DETECT)
        self.assertEqual(chunks[0].aliases, ("str_detect",))

    def test_ids_are_unique_and_deterministic(self):
        first = chunk_topic(STR_PAD)
        second = chunk_topic(STR_PAD)
        self.assertEqual([c.id for c in first], [c.id for c in second])
        self.assertEqual(len({c.id for c in first}), len(first))

    def test_index_and_count_are_consistent(self):
        chunks = chunk_topic(long_record(), max_chars=600)
        self.assertEqual([c.index for c in chunks], list(range(len(chunks))))
        self.assertTrue(all(c.count == len(chunks) for c in chunks))

    def test_long_sections_respect_the_size_limit_and_lose_nothing(self):
        for limit in (400, 600, 1500):
            chunks = chunk_topic(long_record(), max_chars=limit)
            self.assertGreater(len(chunks), 1 if limit < 1500 else 0)
            for chunk in chunks:
                self.assertLessEqual(len(chunk.text), limit)
            joined = "\n".join(c.text for c in chunks)
            for i in range(40):
                self.assertIn(f"arg_{i}:", joined)

    def test_one_huge_line_without_spaces_terminates(self):
        record = long_record(1)
        record["text"] = "f   package:p   R Documentation\n\nT\n\nExamples:\n\n     " + "x" * 5000 + "\n"
        chunks = chunk_topic(record, max_chars=500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c.text) <= 500 for c in chunks))

    def test_payload_has_what_retrieval_needs(self):
        payload = chunk_topic(STR_PAD)[0].payload()
        for key in ("package", "version", "topic", "title", "aliases", "section", "chunk_index", "chunk_count", "text"):
            self.assertIn(key, payload)
        self.assertEqual(payload["package"], "stringr")
        self.assertEqual(payload["version"], "1.5.1")

    def test_topic_without_text_gives_no_chunks(self):
        self.assertEqual(chunk_topic({"package": "p", "name": "n", "text": ""}), [])


class OtherRecordsTest(unittest.TestCase):
    def test_description_record(self):
        chunks = chunk_description(RECORDS[0])
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].text.startswith("stringr (package overview)"))
        self.assertIn("wrappers around the 'stringi' package", chunks[0].text)
        self.assertEqual(chunks[0].topic, "stringr-description")

    def test_empty_description_gives_no_chunks(self):
        self.assertEqual(chunk_description({"package": "p", "title": "", "description": ""}), [])

    def test_unknown_record_type_is_ignored(self):
        self.assertEqual(chunk_record({"type": "vignette", "package": "p"}), [])


class SplitTextTest(unittest.TestCase):
    def test_short_text_is_returned_whole(self):
        self.assertEqual(split_text("abc", 10), ["abc"])

    def test_prefers_paragraph_boundaries(self):
        pieces = split_text("aaaa\n\nbbbb\n\ncccc", 10)
        self.assertEqual(pieces, ["aaaa\n\nbbbb", "cccc"])


if __name__ == "__main__":
    unittest.main()
