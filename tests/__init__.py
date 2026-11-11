"""Tests, by level (each folder says what it covers and what it needs):

    unit/         logic without I/O                                   seconds, no Docker
    integration/  our code against real infrastructure (Qdrant, HTTP)  needs Docker (testcontainers)
    contract/     the API between the R client and the Python service  Python here, R in contract/r/
    e2e/          the whole stack: R -> API -> Ollama -> Qdrant        needs `make up`; minutes

Shared helpers stay here: fixtures.py (sample data, what the R client sends), fakes.py
(embedder, fake Ollama server), qdrant.py (test Qdrant container).
"""
