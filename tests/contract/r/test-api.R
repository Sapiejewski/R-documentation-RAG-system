# The conversation with the rag API (api.R), against fake_api() from helper.R.

test_that("every request has the shape of the shared example the Python side accepts", {
  api <- fake_api(send = PKG)
  httr2::local_mocked_responses(api$handler)

  suppressMessages(sync_library(LIB))

  for (request in api$requests) {
    expect_equal(shape(as_sent(request$body)), shape(example_for(request$path)), label = request$path)
  }
})

test_that("only the packages in the plan are sent: begin, pages in batches, commit", {
  api <- fake_api(send = PKG, batch_size = 2)
  httr2::local_mocked_responses(api$handler)

  failed <- suppressMessages(sync_library(LIB))

  expect_length(failed, 0)
  n_pages <- length(help_pages(PKG, LIB))
  expect_equal(paths(api), c(
    "/sync", "/packages/begin", rep("/packages/pages", ceiling(n_pages / 2)), "/packages/commit"
  ))
  batches <- Filter(function(r) r$path == "/packages/pages", api$requests)
  sizes <- vapply(batches, function(r) length(r$body$pages), 0)
  expect_true(all(sizes <= 2))
  expect_equal(sum(sizes), n_pages)
})

test_that("the manifest goes to /sync, and every package request names the installation", {
  api <- fake_api(send = PKG)
  httr2::local_mocked_responses(api$handler)

  suppressMessages(sync_library(LIB))

  sync <- api$requests[[1]]$body
  expect_equal(sync$library, LIB)
  expect_equal(sync$packages, library_manifest(LIB))
  row <- sync$packages[sync$packages$package == PKG, ]
  for (request in api$requests[-1]) {
    expect_equal(request$body$installation,
                 list(library = LIB, package = PKG, version = row$version, built = row$built))
  }
})

test_that("nothing to send means a single request", {
  api <- fake_api(send = character(0))
  httr2::local_mocked_responses(api$handler)

  suppressMessages(sync_library(LIB))

  expect_equal(paths(api), "/sync")
})

test_that("a failing package is not committed and does not stop the others", {
  api <- fake_api(send = c("compiler", "tcltk"), failing_package = "compiler")
  httr2::local_mocked_responses(api$handler)

  messages <- capture_messages(failed <- sync_library(LIB))

  expect_equal(failed, "compiler")
  expect_match(paste(messages, collapse = ""), "compiler: FAILED.*invalid field")
  committed <- Filter(function(r) r$path == "/packages/commit", api$requests)
  expect_equal(vapply(committed, function(r) r$body$installation$package, ""), "tcltk")
})

test_that("an API error shows the service's explanation", {
  api <- fake_api(send = character(0), failing_package = PKG)
  httr2::local_mocked_responses(api$handler)

  expect_error(api_post("/packages/commit", list(installation = list(package = PKG))), "invalid field")
})
