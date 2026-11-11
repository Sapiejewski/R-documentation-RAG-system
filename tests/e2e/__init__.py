"""End-to-end tests: the whole stack in Docker, as a user runs it: R client -> rag API ->
Ollama (real embeddings) -> Qdrant. Need `make up` (skipped otherwise); take minutes, so they
are not part of `make test` -- run with `make test-e2e`.
"""
