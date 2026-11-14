"""Sample data as the R client sends it: an installation, its overview and help pages
(rendered the way tools::Rd2txt renders them; shaped like rag.schemas.HelpPage)."""

from rag.schemas import Installation

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

STRINGR = Installation(
    library="user", package="stringr", version="1.5.1", built="R 4.5.1; ; 2025-01-10 10:00:00 UTC; unix", extractor=1
)

OVERVIEW = {
    "title": "Simple, Consistent Wrappers for Common String Operations",
    "description": "A consistent, simple and easy to use set of wrappers around the 'stringi' package.",
}

PAGES = [
    {
        "name": "str_pad",
        "title": "Pad a string to minimum width",
        "aliases": ["str_pad"],
        "keywords": [],
        "text": STR_PAD_TEXT,
    },
    {
        "name": "str_trim",
        "title": "Trim whitespace from a string",
        "aliases": ["str_trim", "str_squish"],
        "keywords": [],
        "text": STR_TRIM_TEXT,
    },
    {
        "name": "str_detect",
        "title": "Detect the presence or absence of a pattern in a string",
        "aliases": "str_detect",  # jsonlite writes a single alias as a bare string
        "keywords": [],
        "text": STR_DETECT_TEXT,
    },
]


def manifest(*installations: Installation, library: str = "user", origin: str = "host:test") -> dict:
    """The body of POST /sync: what the R client lists for one library."""
    return {
        "library": library,
        "origin": origin,
        "extractor": installations[0].extractor if installations else 1,
        "packages": [{"package": i.package, "version": i.version, "built": i.built} for i in installations],
    }


def send_package(client, inst: Installation = STRINGR, pages: list[dict] = PAGES) -> dict:
    """What the R client does over HTTP (client: a FastAPI TestClient) for one package the plan
    asked for: begin, pages in batches of the plan's batch_size, commit. Returns the commit answer."""
    installation = inst.model_dump()
    client.post("/packages/begin", json={"installation": installation} | OVERVIEW).raise_for_status()
    batch_size = client.post("/sync", json=manifest(inst, library=inst.library)).json()["batch_size"]
    for start in range(0, len(pages), batch_size):
        batch = pages[start : start + batch_size]
        client.post("/packages/pages", json={"installation": installation, "pages": batch}).raise_for_status()
    response = client.post("/packages/commit", json={"installation": installation})
    response.raise_for_status()
    return response.json()


def sync_package(indexer, inst: Installation = STRINGR, pages: list[dict] = PAGES, overview: dict = OVERVIEW) -> int:
    """What the R client does for one package the plan asked for. Returns the committed chunk count."""
    indexer.begin(inst, overview["title"], overview["description"])
    indexer.add_pages(inst, pages)
    return indexer.commit(inst)
