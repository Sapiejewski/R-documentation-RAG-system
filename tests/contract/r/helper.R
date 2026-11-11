# testthat runs helper*.R before the tests, with this folder as the working directory:
# load the code under test.
for (file in c("config.R", "extract.R", "api.R", "setup.R")) {
  source(file.path("..", "..", "..", "src", "client", file))
}

# A small package that every R installation has, in the library of the R running the tests.
PKG <- "compiler"
LIB <- .Library

# A stand-in for the rag API: answers like the real one and records every request
# (api$requests: list of list(path, body)). Requests about `failing_package` get a 422.
fake_api <- function(send, batch_size = 2, failing_package = "") {
  api <- new.env() # an environment, so the handler can add to api$requests
  api$requests <- list()
  api$handler <- function(req) { # httr2 requires the argument to be called `req`
    path <- httr2::url_parse(req$url)$path
    body <- req$body$data
    api$requests[[length(api$requests) + 1]] <- list(path = path, body = body)
    if (identical(body$installation$package, failing_package)) {
      return(httr2::response(
        status_code = 422,
        headers = list("Content-Type" = "application/json"),
        body = charToRaw('{"detail": "invalid field"}')
      ))
    }
    answer <- switch(path,
      "/sync" = list(send = as.list(send), removed = list(), unchanged = 0, batch_size = batch_size),
      "/packages/commit" = list(chunks = 7),
      list(chunks = 1, embedded = 1, reused = 0, seconds = 0) # begin, pages
    )
    httr2::response_json(body = answer)
  }
  api
}

# The paths of the recorded requests, in order.
paths <- function(api) vapply(api$requests, function(r) r$path, "")

# The shared example request for an API path (tests/contract/examples/), e.g. "/sync" -> sync.json.
example_for <- function(path) {
  jsonlite::read_json(file.path("..", "examples", paste0(basename(path), ".json")), simplifyVector = FALSE)
}

# A request body as the API receives it: serialized like httr2 does (req_body_json), parsed back.
as_sent <- function(body) {
  jsonlite::fromJSON(jsonlite::toJSON(body, auto_unbox = TRUE), simplifyVector = FALSE)
}

# The shape of a parsed JSON value: field names all the way down, values reduced to "value",
# arrays of values to "array", arrays of objects to the shape of their first object.
# Two requests have the same shape if they have the same fields of the same kinds.
shape <- function(x) {
  if (!is.list(x)) return("value")
  if (is.null(names(x))) { # a JSON array
    if (length(x) > 0 && is.list(x[[1]]) && !is.null(names(x[[1]]))) return(list(shape(x[[1]])))
    return("array")
  }
  lapply(x[sort(names(x))], shape)
}
