"""Sample extraction output, written the way tools::Rd2txt renders help pages."""

import json
from pathlib import Path

STR_PAD_TEXT = """\
str_pad                package:stringr                R Documentation

Pad a string to minimum width

Description:

     Pad a string to a minimum width, adding characters on the left,
     right, or both sides.

Usage:

     str_pad(
       string,
       width,
       side = c("left", "right", "both"),
       pad = " ",
       use_width = TRUE
     )

Arguments:

  string: Input vector. Either a character vector, or something
          coercible to one.

   width: Minimum width of padded strings.

    side: Side on which padding character is added (left, right or
          both).

     pad: Single padding character (default is a space).

Value:

     A character vector the same length as 'string'.

See Also:

     'str_trim()' to remove whitespace.

Examples:

     rbind(
       str_pad("hadley", 30, "left"),
       str_pad("hadley", 30, "right"),
       str_pad("hadley", 30, "both")
     )

     # Pad with zeros
     str_pad(1:3, 3, pad = "0")

Author(s):

     Somebody <somebody@example.com>
"""

STR_TRIM_TEXT = """\
str_trim               package:stringr               R Documentation

Trim whitespace from a string

Description:

     'str_trim()' removes whitespace from start and end of string;
     'str_squish()' removes whitespace at the start and end, and
     replaces all internal whitespace with a single space.

Usage:

     str_trim(string, side = c("both", "left", "right"))

     str_squish(string)

Arguments:

  string: Input vector.

    side: Side on which to remove whitespace.

Value:

     A character vector the same length as 'string'.

Examples:

     str_trim("  String with trailing and leading white space\\t")
     str_squish("  String with  excess,  trailing and leading white   space\\t")
"""

STR_DETECT_TEXT = """\
str_detect              package:stringr              R Documentation

Detect the presence or absence of a pattern in a string

Description:

     'str_detect()' returns a logical vector with 'TRUE' for each
     element of 'string' that matches 'pattern' and 'FALSE' otherwise.

Usage:

     str_detect(string, pattern, negate = FALSE)

Arguments:

  string: Input vector.

 pattern: Pattern to look for.

  negate: If 'TRUE', return non-matching elements.

Value:

     A logical vector the same length as 'string'.

Examples:

     fruit <- c("apple", "banana", "pear", "pineapple")
     str_detect(fruit, "a")
     str_detect(fruit, "^a")
"""

RECORDS = [
    {
        "type": "description",
        "package": "stringr",
        "version": "1.5.1",
        "title": "Simple, Consistent Wrappers for Common String Operations",
        "description": "A consistent, simple and easy to use set of wrappers around the 'stringi' package.",
    },
    {
        "type": "topic",
        "package": "stringr",
        "version": "1.5.1",
        "name": "str_pad",
        "title": "Pad a string to minimum width",
        "aliases": ["str_pad"],
        "keywords": [],
        "text": STR_PAD_TEXT,
    },
    {
        "type": "topic",
        "package": "stringr",
        "version": "1.5.1",
        "name": "str_trim",
        "title": "Trim whitespace from a string",
        "aliases": ["str_trim", "str_squish"],
        "keywords": [],
        "text": STR_TRIM_TEXT,
    },
    {
        "type": "topic",
        "package": "stringr",
        "version": "1.5.1",
        "name": "str_detect",
        "title": "Detect the presence or absence of a pattern in a string",
        "aliases": "str_detect",  # jsonlite writes a single alias as a bare string
        "keywords": [],
        "text": STR_DETECT_TEXT,
    },
]


def write_extracted(data_dir: Path, package: str = "stringr", records: list[dict] | None = None) -> Path:
    path = data_dir / "extracted" / f"{package}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = RECORDS if records is None else records
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path
