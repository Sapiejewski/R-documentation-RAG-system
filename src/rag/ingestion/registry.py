"""The record of what is in the index: the libraries it knows (`KnownLibrary`) and the packages
indexed from each (`IndexedPackage`, one per library/package).

The R client reports what is installed (`Installation`); the registry remembers what has been
indexed. Comparing the two tells a sync what to (re)index and what to drop.
"""

from typing import Protocol

from rag.schemas import IndexedPackage, KnownLibrary


class PackageRegistry(Protocol):
    def indexed(self, library: str) -> dict[str, IndexedPackage]: ...
    def save(self, entry: IndexedPackage) -> None: ...
    def remove(self, library: str, package: str) -> None: ...
    def libraries(self) -> list[KnownLibrary]: ...
    def save_library(self, library: KnownLibrary) -> None: ...
    def forget_library(self, library: str) -> None:
        """Remove the library and every package entry of it."""
        ...


class MemoryRegistry:
    """Registry held in dicts. For tests."""

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], IndexedPackage] = {}
        self.known: dict[str, KnownLibrary] = {}

    def libraries(self) -> list[KnownLibrary]:
        return sorted(self.known.values(), key=lambda lib: lib.library)

    def save_library(self, library: KnownLibrary) -> None:
        self.known[library.library] = library

    def forget_library(self, library: str) -> None:
        self.known.pop(library, None)
        self.entries = {key: e for key, e in self.entries.items() if key[0] != library}

    def indexed(self, library: str) -> dict[str, IndexedPackage]:
        return {package: e for (lib, package), e in self.entries.items() if lib == library}

    def save(self, entry: IndexedPackage) -> None:
        self.entries[(entry.installation.library, entry.installation.package)] = entry

    def remove(self, library: str, package: str) -> None:
        self.entries.pop((library, package), None)
