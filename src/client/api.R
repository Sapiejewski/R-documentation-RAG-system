# Talking to the rag API (src/rag/api): the R side of a library sync. Sourced by main.R.
#
# The service decides everything; R only answers its questions:
#   1. POST /sync              here is what is installed      -> which packages to send
#   2. POST /packages/begin    for each of them: its overview
#   3. POST /packages/pages    its help pages, batch_size at a time
#   4. POST /packages/commit   done: switch searches to this version
# A package that fails half-way is simply not committed: its previous version stays
# searchable, and the service asks for it again on the next sync.

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
  plan <- api_post("/sync", list(library = lib, packages = manifest))
  message(sprintf("%s: %d packages | %d to send, %d unchanged, %d removed",
                  lib, nrow(manifest), length(plan$send), plan$unchanged, length(plan$removed)))

  failed <- character(0)
  for (pkg in plan$send) {
    row <- manifest[manifest$package == pkg, ]
    installation <- list(library = lib, package = pkg, version = row$version, built = row$built)
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

# Sync the given libraries (main.R: the ones chosen in `init`, see selected_libraries()).
sync_libraries <- function(libraries) {
  if (length(libraries) == 0) stop("no R library to index. Choose them: ", command_for("init"), call. = FALSE)
  require_httr2()
  health <- tryCatch(api_get("/health"), error = function(e) NULL)
  if (is.null(health)) stop("the rag API does not answer at ", rag_url(), ". Start it: ", command_for("up"), call. = FALSE)
  failed <- 0
  for (lib in libraries) {
    failed <- failed + length(sync_library(lib))
  }
  if (failed > 0) stop(failed, " package(s) failed, see above", call. = FALSE)
}
