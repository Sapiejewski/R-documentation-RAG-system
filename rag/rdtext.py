"""Split the plain-text rendering of an Rd help page (tools::Rd2txt) into sections.

A rendered page looks like this (body text is indented, section titles are not):

    str_pad                package:stringr                R Documentation

    Pad a string to minimum width

    Description:

         Pad a string to a minimum width.

    Usage:

         str_pad(string, width, side = "left", pad = " ")

    Arguments:

      string: A character vector.
"""

import re
import textwrap
from dataclasses import dataclass

# A section title: starts in column 0 with a capital letter and ends with a colon.
_SECTION_TITLE = re.compile(r"^[A-Z][^\n:]{0,60}:\s*$")
_BANNER = re.compile(r"R Documentation\s*$")


@dataclass(frozen=True)
class Section:
    title: str
    body: str


def _clean(lines: list[str]) -> str:
    body = textwrap.dedent("\n".join(line.rstrip() for line in lines))
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip("\n")


def parse_sections(text: str) -> list[Section]:
    """Return the sections of a rendered help page, dropping the banner and title."""
    sections: list[Section] = []
    title: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if title is not None:
            body = _clean(buffer)
            if body:
                sections.append(Section(title, body))

    for line in text.splitlines():
        if title is None and _BANNER.search(line):
            continue
        if _SECTION_TITLE.match(line):
            flush()
            title = line.strip().rstrip(":").strip()
            buffer = []
        elif title is not None:
            buffer.append(line)
    flush()
    return sections
