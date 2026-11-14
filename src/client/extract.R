# Reading installed R packages: what is installed, and their help pages as text.
# No network here (that is api.R). Sourced by main.R.
#
# It only reads files of an installed package (DESCRIPTION and the compiled help
# database help/<pkg>.rdb); it never loads the package. That is why it works for
# packages installed by a different R version than the one running here.

tools::Rd2txt_options(underline_titles = FALSE, width = 80)

# All pieces of x as one string, with runs of whitespace collapsed to one space.
squish <- function(x) trimws(gsub("[[:space:]]+", " ", paste(unlist(x), collapse = "")))

# The Rd tag of one element of a help page (e.g. "\\title"), or "" if it has none.
tag_of <- function(element) {
  tag <- attr(element, "Rd_tag")
  if (is.null(tag)) "" else tag
}

# Packages installed in one library folder, read straight from their DESCRIPTION files:
# a data frame with columns package, version, built.
# (Not installed.packages(): its "Built" column holds only the R version, not the
# build timestamp, so it cannot tell a reinstall of the same version apart.)
library_manifest <- function(lib) {
  files <- Sys.glob(file.path(lib, "*", "DESCRIPTION"))
  fields <- c("Package", "Version", "Built")
  rows <- lapply(files, function(f) read.dcf(f, fields = fields)[1, ])
  rows <- Filter(function(row) !anyNA(row), rows) # source folders etc. without a "Built" field
  data.frame(
    package = vapply(rows, `[[`, "", "Package"),
    version = vapply(rows, `[[`, "", "Version"),
    built = vapply(rows, `[[`, "", "Built"),
    stringsAsFactors = FALSE
  )
}

# Title and description of a package, from its DESCRIPTION.
package_overview <- function(pkg, lib) {
  desc <- utils::packageDescription(pkg, lib.loc = lib)
  list(title = squish(desc$Title), description = squish(desc$Description))
}

# One help page as plain text, the way R's help() shows it in a terminal.
render_help_page <- function(rd, pkg) {
  out <- tempfile(fileext = ".txt")
  on.exit(unlink(out))
  tools::Rd2txt(rd, out = out, package = pkg, outputEncoding = "UTF-8")
  paste(readLines(out, encoding = "UTF-8", warn = FALSE), collapse = "\n")
}

# Every help page of a package (skipping pages marked `internal`), as a list of
# list(name, title, aliases, keywords, text) -- the HelpPage schema of the rag API.
help_pages <- function(pkg, lib) {
  # Some pages run R code while rendering (\Sexpr), which loads the package itself (e.g. generics
  # lists its methods). R finds packages only on .libPaths(), so put this library first for now.
  old_paths <- .libPaths()
  .libPaths(c(lib, old_paths))
  on.exit(.libPaths(old_paths))

  pages <- list()
  db <- tools::Rd_db(pkg, lib.loc = lib)
  for (file_name in names(db)) {
    rd <- db[[file_name]]
    elements <- unclass(rd)
    tags <- vapply(elements, tag_of, character(1))
    texts <- function(tag) unique(vapply(elements[tags == tag], squish, character(1), USE.NAMES = FALSE))
    keywords <- texts("\\keyword")
    if ("internal" %in% keywords) next
    text <- tryCatch(render_help_page(rd, pkg), error = function(e) {
      message("  ", pkg, ": skipped ", file_name, " (", conditionMessage(e), ")")
      NULL
    })
    if (is.null(text)) next
    pages[[length(pages) + 1]] <- list(
      name = squish(elements[tags == "\\name"]),
      title = squish(elements[tags == "\\title"]),
      aliases = I(texts("\\alias")), # I(): stays a JSON array even with one alias
      keywords = I(keywords),
      text = text
    )
  }
  pages
}

# Experiments: install packages into the Docker-only library from the image's
# dated CRAN snapshot, so the same versions come back on every machine.
install_packages <- function(packages, lib = "/libraries/docker") {
  if (length(packages) == 0) stop("usage: main.R install <package>...")
  utils::install.packages(packages, lib = lib)
  missing <- setdiff(packages, rownames(utils::installed.packages(lib.loc = lib)))
  if (length(missing)) stop("Could not install: ", paste(missing, collapse = ", "), ". Is the name correct?")
}
