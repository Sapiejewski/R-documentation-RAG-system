"""The CLI when the services are not there: a clean error with a hint, not a traceback.

CLI commands against a real Qdrant are in test_qdrant.py (CliOverQdrantTest).
"""

import contextlib
import io
import os
import unittest
from unittest import mock

from rag.cli import main


class CliTest(unittest.TestCase):
    def test_unreachable_services_are_a_clean_error(self):
        env = {"OLLAMA_URL": "http://127.0.0.1:9", "QDRANT_URL": "http://127.0.0.1:9"}
        err = io.StringIO()
        with (
            mock.patch.dict(os.environ, env),
            contextlib.redirect_stderr(err),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = main(["search", "pad a string"])
        self.assertEqual(code, 1)
        self.assertIn("make up", err.getvalue())


if __name__ == "__main__":
    unittest.main()
