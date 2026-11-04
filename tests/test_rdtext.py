import unittest

from rag.rdtext import parse_sections
from tests.fixtures import STR_PAD_TEXT


class ParseSectionsTest(unittest.TestCase):
    def setUp(self):
        self.sections = parse_sections(STR_PAD_TEXT)
        self.by_title = {s.title: s.body for s in self.sections}

    def test_finds_sections_in_order(self):
        titles = [s.title for s in self.sections]
        self.assertEqual(titles, ["Description", "Usage", "Arguments", "Value", "See Also", "Examples", "Author(s)"])

    def test_banner_and_title_are_not_part_of_any_section(self):
        for section in self.sections:
            self.assertNotIn("R Documentation", section.body)
            self.assertNotIn("Pad a string to minimum width", section.body)

    def test_bodies_are_dedented(self):
        self.assertTrue(self.by_title["Description"].startswith("Pad a string to a minimum width"))
        self.assertTrue(self.by_title["Usage"].startswith("str_pad("))

    def test_keeps_relative_indentation_in_code(self):
        self.assertIn("\n  string,\n  width,", self.by_title["Usage"])

    def test_argument_items_stay_together(self):
        arguments = self.by_title["Arguments"]
        for name in ("string:", "width:", "side:", "pad:"):
            self.assertIn(name, arguments)

    def test_empty_and_sectionless_text(self):
        self.assertEqual(parse_sections(""), [])
        self.assertEqual(parse_sections("just some text\nwith no sections"), [])

    def test_empty_sections_are_dropped(self):
        text = "x   package:p   R Documentation\n\nTitle\n\nDescription:\n\nUsage:\n\n     f(x)\n"
        self.assertEqual([s.title for s in parse_sections(text)], ["Usage"])


if __name__ == "__main__":
    unittest.main()
