"""The validation the HTTP API relies on: bad client data is rejected before our code runs."""

import unittest

from pydantic import ValidationError

from rag.schemas import Installation
from tests.fixtures import STRINGR


class InstallationTest(unittest.TestCase):
    def test_accepts_what_the_r_client_sends(self):
        data = {"library": "user", "package": "stringr", "version": "1.5.1", "built": "R 4.5.1; ; 2025; unix"}
        self.assertEqual(Installation.model_validate(data).package, "stringr")

    def test_rejects_missing_empty_and_unknown_fields(self):
        good = STRINGR.model_dump()
        for bad in (
            {k: v for k, v in good.items() if k != "built"},  # missing
            good | {"package": ""},  # empty
            good | {"bulit": "typo"},  # unknown field, e.g. a typo in the client
        ):
            with self.assertRaises(ValidationError):
                Installation.model_validate(bad)

    def test_is_immutable_and_compares_by_value(self):
        with self.assertRaises(ValidationError):
            STRINGR.version = "2.0"
        self.assertEqual(STRINGR, Installation.model_validate(STRINGR.model_dump()))


if __name__ == "__main__":
    unittest.main()
