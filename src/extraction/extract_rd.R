#!/usr/bin/env Rscript
# Dump the help pages of an R package to JSON Lines (one record per help topic).
#
#   Rscript extract_rd.R <package> [output_dir]
#
# Normally run through Docker:  make extract PKG=stringr
#
# Output: <output_dir>/<package>.jsonl with
#   {"type":"description", package, version, title, description}      (one)
#   {"type":"topic", package, version, name, title, aliases, keywords, text}
# where `text` is R's own plain-text rendering of the help page (tools::Rd2txt).

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: extract_rd.R <package> [output_dir]")
pkg <- args[[1]]
out_dir <- if (length(args) >= 2) args[[2]] else "data/extracted"

# --- make sure a CRAN mirror is configured, then install what we need --------
repos <- getOption("repos")
if (is.null(repos) || is.na(repos["CRAN"]) || repos["CRAN"] == "@CRAN@") {
  options(repos = c(CRAN = "https://cloud.r-project.org"))
}

ensure <- function(p) {
  if (!requireNamespace(p, quietly = TRUE)) {
    message("Installing '", p, "' ...")
    install.packages(p, quiet = TRUE)
    if (!requireNamespace(p, quietly = TRUE)) {
      stop("Could not install package '", p, "'. Is the name correct?")
    }
  }
}
ensure("jsonlite")
ensure(pkg)

version <- as.character(utils::packageVersion(pkg))
desc <- utils::packageDescription(pkg)

# --- helpers -----------------------------------------------------------------
squish <- function(x) trimws(gsub("[[:space:]]+", " ", paste(unlist(x), collapse = "")))
tag_of <- function(e) {
  t <- attr(e, "Rd_tag")
  if (is.null(t)) "" else t
}
# Plain-text content of every top-level element with the given Rd tag.
texts_of <- function(elements, tags, tag) {
  vapply(elements[tags == tag], squish, character(1), USE.NAMES = FALSE)
}

tools::Rd2txt_options(underline_titles = FALSE, width = 80)
tmp <- tempfile(fileext = ".txt")
render <- function(rd) {
  tools::Rd2txt(rd, out = tmp, package = pkg, outputEncoding = "UTF-8")
  paste(readLines(tmp, encoding = "UTF-8", warn = FALSE), collapse = "\n")
}

# --- write the records -------------------------------------------------------
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
out_path <- file.path(out_dir, paste0(pkg, ".jsonl"))
con <- file(out_path, open = "wb")
on.exit(close(con), add = TRUE)

emit <- function(rec) {
  json <- jsonlite::toJSON(rec, auto_unbox = TRUE, null = "null", na = "null")
  writeLines(as.character(json), con, useBytes = TRUE)
}

emit(list(
  type = "description", package = pkg, version = version,
  title = squish(desc$Title), description = squish(desc$Description)
))

db <- tools::Rd_db(pkg)
n_topics <- 0L
n_internal <- 0L
n_failed <- 0L

for (file_name in names(db)) {
  rd <- db[[file_name]]
  result <- tryCatch({
    elements <- unclass(rd)
    tags <- vapply(elements, tag_of, character(1))
    name <- squish(elements[tags == "\\name"])
    title <- squish(elements[tags == "\\title"])
    aliases <- unique(texts_of(elements, tags, "\\alias"))
    keywords <- unique(texts_of(elements, tags, "\\keyword"))
    if ("internal" %in% keywords) {
      "internal"
    } else {
      emit(list(
        type = "topic", package = pkg, version = version,
        name = name, title = title,
        aliases = I(aliases), keywords = I(keywords),
        text = render(rd)
      ))
      "ok"
    }
  }, error = function(e) {
    message("  skipped ", file_name, ": ", conditionMessage(e))
    "failed"
  })
  if (result == "ok") n_topics <- n_topics + 1L
  if (result == "internal") n_internal <- n_internal + 1L
  if (result == "failed") n_failed <- n_failed + 1L
}

message(sprintf(
  "%s %s: wrote %d help topics (%d internal skipped, %d failed) to %s",
  pkg, version, n_topics, n_internal, n_failed, out_path
))
if (n_topics == 0L) stop("No help topics were extracted for '", pkg, "'.")
