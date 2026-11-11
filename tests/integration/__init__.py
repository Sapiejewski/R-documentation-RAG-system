"""Integration tests: our code against real infrastructure. Qdrant is a real container
(testcontainers, see tests/qdrant.py; skipped without Docker); HTTP clients talk to a local
fake Ollama server (real sockets and JSON, deterministic answers).
"""
