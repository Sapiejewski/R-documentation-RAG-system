# Turning installed R packages into JSON Lines records. Sourced by main.R.
#
# Extraction only reads files of an installed package (DESCRIPTION and the compiled
# help database help/<pkg>.rdb); it never loads the package. That is why it works
# for packages installed by a different R version than the one running here.
#
# Output: one file per package, data/extracted/<library>/<package>.jsonl:
#   line 1:  {"type":"description", package, version, built, library, title, description}
#   then:    {"type":"topic", package, version, name, title, aliases, keywords, text}
# where `text` is R's own plain-text rendering of the help page (tools::Rd2txt).
# `built` changes on every reinstall, so (version, built) identifies an installation.

tools::Rd2txt_options(underline_titles = FALSE, width = 80)

squish <- function(x) trimws(gsub("[[:space:]]+", " ", paste(unlist(x), collapse = "")))

tag_of <- function(element) {
  tag <- attr(element, "Rd_tag")
  if (is.null(tag)) "" else tag
}

# Packages installed in one library folder, read straight from their DESCRIPTION files.
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

render_help_page <- function(rd, pkg) {
  out <- tempfile(fileext = ".txt")
  on.exit(unlink(out))
  tools::Rd2txt(rd, out = out, package = pkg, outputEncoding = "UTF-8")
  paste(readLines(out, encoding = "UTF-8", warn = FALSE), collapse = "\n")
}

# One record per help page, skipping pages marked `internal`.
topic_records <- function(pkg, lib, version) {
  records <- list()
  db <- tools::Rd_db(pkg, lib.loc = lib)
  for (file_name in names(db)) {
    rd <- db[[file_name]]
    elements <- unclass(rd)
    tags <- vapply(elements, tag_of, character(1))
    texts <- function(tag) unique(vapply(elements[tags == tag], squish, character(1), USE.NAMES = FALSE))
    keywords <- texts("\\keyword")
    if ("internal" %in% keywords) next
    page <- tryCatch(render_help_page(rd, pkg), error = function(e) {
      message("  ", pkg, ": skipped ", file_name, " (", conditionMessage(e), ")")
      NULL
    })
    if (is.null(page)) next
    records[[length(records) + 1]] <- list(
      type = "topic", package = pkg, version = version,
      name = squish(elements[tags == "\\name"]), title = squish(elements[tags == "\\title"]),
      aliases = I(texts("\\alias")), keywords = I(keywords), text = page
    )
  }
  records
}

# Write records to a temporary file first, then rename it: a half-written file
# (e.g. the container was stopped) never looks like a finished extraction.
write_jsonl <- function(records, path) {
  partial <- paste0(path, ".partial")
  con <- file(partial, open = "wb")
  for (record in records) {
    json <- jsonlite::toJSON(record, auto_unbox = TRUE, null = "null", na = "null")
    writeLines(as.character(json), con, useBytes = TRUE)
  }
  close(con)
  file.rename(partial, path)
}

extract_package <- function(pkg, lib, library_name, path) {
  desc <- utils::packageDescription(pkg, lib.loc = lib)
  header <- list(
    type = "description", package = pkg, version = desc$Version, built = desc$Built,
    library = library_name, title = squish(desc$Title), description = squish(desc$Description)
  )
  topics <- topic_records(pkg, lib, desc$Version)
  write_jsonl(c(list(header), topics), path)
  length(topics)
}

# TRUE if `path` already holds the extraction of exactly this installation.
is_up_to_date <- function(path, version, built) {
  if (!file.exists(path)) {
    return(FALSE)
  }
  header <- jsonlite::fromJSON(readLines(path, n = 1, warn = FALSE))
  identical(header$version, version) && identical(header$built, built)
}

# Bring data/extracted/<library>/ in line with every library mounted under
# `libraries_dir`: extract new and reinstalled packages, delete removed ones.
sync_libraries <- function(libraries_dir = "/libraries", out_dir = "data/extracted") {
  libraries <- list.dirs(libraries_dir, recursive = FALSE)
  for (lib in libraries) {
    name <- basename(lib)
    lib_out <- file.path(out_dir, name)
    dir.create(lib_out, recursive = TRUE, showWarnings = FALSE)
    manifest <- library_manifest(lib)

    extracted <- 0L
    for (i in seq_len(nrow(manifest))) {
      pkg <- manifest$package[[i]]
      path <- file.path(lib_out, paste0(pkg, ".jsonl"))
      if (is_up_to_date(path, manifest$version[[i]], manifest$built[[i]])) next
      started <- Sys.time()
      n <- tryCatch(extract_package(pkg, lib, name, path), error = function(e) {
        message("  ", name, "/", pkg, ": FAILED (", conditionMessage(e), ")")
        NA
      })
      if (is.na(n)) next
      extracted <- extracted + 1L
      message(sprintf("  %s/%s %s: %d help pages (%.1fs)", name, pkg, manifest$version[[i]], n,
                      as.numeric(Sys.time() - started, units = "secs")))
    }

    on_disk <- sub("\\.jsonl$", "", list.files(lib_out, pattern = "\\.jsonl$"))
    removed <- setdiff(on_disk, manifest$package)
    unlink(file.path(lib_out, paste0(removed, ".jsonl")))
    for (pkg in removed) message("  ", name, "/", pkg, ": removed")

    message(sprintf("%s: %d packages | %d extracted, %d unchanged, %d removed",
                    name, nrow(manifest), extracted, nrow(manifest) - extracted, length(removed)))
  }

  # Outputs of libraries that are no longer mounted.
  for (stale in setdiff(list.dirs(out_dir, full.names = FALSE, recursive = FALSE), basename(libraries))) {
    unlink(file.path(out_dir, stale), recursive = TRUE)
    message(stale, ": library no longer mounted, its extracted files were removed")
  }
}

# Experiments: install packages into the Docker-only library from the image's
# dated CRAN snapshot, so the same versions come back on every machine.
install_packages <- function(packages, lib = "/libraries/docker") {
  if (length(packages) == 0) stop("usage: main.R install <package>...")
  utils::install.packages(packages, lib = lib)
  missing <- setdiff(packages, rownames(utils::installed.packages(lib.loc = lib)))
  if (length(missing)) stop("Could not install: ", paste(missing, collapse = ", "), ". Is the name correct?")
}
