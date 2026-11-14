# Talking to the rag API (src/rag/api): the R side of a library sync. Sourced by main.R.
#
# The service decides everything; R only answers its questions:
#   1. POST /sync              here is what is installed      -> which packages to send
#   2. POST /packages/begin    for each of them: its overview
#   3. POST /packages/pages    its help pages, batch_size at a time
#   4. POST /packages/commit   done: switch searches to this version
# A package that fails half-way is simply not committed: its previous version stays
# searchable, and the service asks for it again on the next sync.
#
# Before that, libraries this client indexed earlier but whose folder is gone are dropped
# (GET /libraries, POST /libraries/forget): see drop_missing_libraries().

# A clear message instead of "there is no package called 'httr2'".
require_httr2 <- function() {
  if (!requireNamespace("httr2", quietly = TRUE)) stop("the R package httr2 is missing. Run: ", command_for("init"), call. = FALSE)
}

# GET from the API (e.g. /health) and return the JSON answer as an R list. No retries: used to
# ask "are you there?", where a quick "no" is the useful answer.
api_get <- function(path, timeout = 5) {
  require_httr2()
  request <- httr2::request(rag_url())
  request <- httr2::req_url_path_append(request, path)
  request <- httr2::req_timeout(request, timeout)
  httr2::resp_body_json(httr2::req_perform(request))
}

# POST `body` as JSON to the API and return the JSON answer as an R list.
api_post <- function(path, body) {
  require_httr2()
  request <- httr2::request(rag_url())
  request <- httr2::req_url_path_append(request, path)
  request <- httr2::req_body_json(request, body)
  # 503 = Ollama or Qdrant is busy or down; a retried request is safe (the API is idempotent).
  request <- httr2::req_retry(request, max_tries = 3)
  # On an error, show the API's explanation (e.g. which field was invalid), not just the status.
  request <- httr2::req_error(request, body = function(response) httr2::resp_body_string(response))
  response <- httr2::req_perform(request)
  httr2::resp_body_json(response)
}

# Send one package the plan asked for: overview, pages in batches, commit.
send_package <- function(installation, lib, batch_size) {
  started <- Sys.time()
  pkg <- installation$package
  overview <- package_overview(pkg, lib)
  api_post("/packages/begin", list(
    installation = installation, title = overview$title, description = overview$description
  ))

  pages <- help_pages(pkg, lib)
  batch_number <- ceiling(seq_along(pages) / batch_size) # 1,1,...,1,2,2,...: batch of each page
  for (batch in split(pages, batch_number)) {
    api_post("/packages/pages", list(installation = installation, pages = unname(batch)))
  }

  committed <- api_post("/packages/commit", list(installation = installation))
  seconds <- as.numeric(Sys.time() - started, units = "secs")
  message(sprintf("  %s/%s %s: %d help pages, %d chunks (%.1fs)",
                  installation$library, pkg, installation$version, length(pages), committed$chunks, seconds))
}

# Sync one library (a folder; its path is its name in the index): report what is installed,
# then send what the service asks for. Returns the packages that failed.
sync_library <- function(lib) {
  manifest <- library_manifest(lib)
  plan <- api_post("/sync", list(
    library = lib, origin = client_origin(), extractor = EXTRACTOR_VERSION, packages = manifest
  ))
  message(sprintf("%s: %d packages | %d to send, %d unchanged, %d removed",
                  lib, nrow(manifest), length(plan$send), plan$unchanged, length(plan$removed)))

  failed <- character(0)
  for (pkg in plan$send) {
    row <- manifest[manifest$package == pkg, ]
    installation <- list(
      library = lib, package = pkg, version = row$version, built = row$built, extractor = EXTRACTOR_VERSION
    )
    sent <- tryCatch({
      send_package(installation, lib, plan$batch_size)
      TRUE
    }, error = function(e) {
      message("  ", lib, "/", pkg, ": FAILED, will be retried on the next sync (", conditionMessage(e), ")")
      FALSE
    })
    if (!sent) failed <- c(failed, pkg)
  }
  failed
}

# Drop one library and all its packages from the index; returns the dropped packages.
forget_library <- function(lib) {
  report <- api_post("/libraries/forget", list(library = lib))
  unlist(report$removed)
}

# Tidy up the libraries this client indexed before (`selected`: the ones it syncs now):
#   folder gone (a deleted renv project, an old R version)  -> dropped from the index
#   folder there, but no longer chosen                      -> kept; the message says how to drop it
# Libraries of another origin are left alone: their folders are on another computer or in a
# container, so "not here" says nothing about them.
drop_missing_libraries <- function(selected) {
  for (entry in api_get("/libraries")$libraries) {
    if (entry$origin != client_origin()) next
    if (!dir.exists(entry$library)) {
      removed <- forget_library(entry$library)
      message(sprintf("%s: the folder no longer exists; removed from the index (%d packages)",
                      entry$library, length(removed)))
    } else if (!(entry$library %in% selected)) {
      message(entry$library, ": indexed, but no longer chosen. To remove it from the index: ",
              forget_command(entry$library))
    }
  }
}

# Sync the given libraries (main.R: the ones chosen in `init`, see selected_libraries()).
sync_libraries <- function(libraries) {
  require_httr2()
  health <- tryCatch(api_get("/health"), error = function(e) NULL)
  if (is.null(health)) stop("the rag API does not answer at ", rag_url(), ". Start it: ", command_for("up"), call. = FALSE)
  # Even with no library left to sync, the ones that disappeared must still be dropped.
  if (length(libraries) == 0) message("No R library to sync. Choose them: ", command_for("init"))
  drop_missing_libraries(libraries)
  failed <- 0
  for (lib in libraries) {
    failed <- failed + length(sync_library(lib))
  }
  if (failed > 0) stop(failed, " package(s) failed, see above", call. = FALSE)
}
