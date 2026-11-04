"""The record of which packages are in the index (one `IndexedPackage` per library/package).

The R client reports what is installed (`Installation`); the registry remembers what has been
indexed. Comparing the two tells a sync what to (re)index and what to drop.
"""

from typing import Protocol

from rag.schemas import IndexedPackage


class PackageRegistry(Protocol):
    def indexed(self, library: str) -> dict[str, IndexedPackage]: ...
    def save(self, entry: IndexedPackage) -> None: ...
    def remove(self, library: str, package: str) -> None: ...


class MemoryRegistry:
    """Registry held in a dict. For tests."""

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], IndexedPackage] = {}

    def indexed(self, library: str) -> dict[str, IndexedPackage]:
        return {package: e for (lib, package), e in self.entries.items() if lib == library}

    def save(self, entry: IndexedPackage) -> None:
        self.entries[(entry.installation.library, entry.installation.package)] = entry

    def remove(self, library: str, package: str) -> None:
        self.entries.pop((library, package), None)
