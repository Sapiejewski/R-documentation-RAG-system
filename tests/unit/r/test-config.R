# Settings of the R client (config.R): .env, the API address, which libraries to index.

test_that(".env values are loaded, but a variable already set wins", {
  path <- withr::local_tempfile(lines = c("# a comment", "", "RDOCS_A=from file", 'RDOCS_B="quoted"', "RDOCS_C=file"))
  withr::local_envvar(RDOCS_A = NA, RDOCS_B = NA, RDOCS_C = "already set")

  load_env_file(path)

  expect_equal(Sys.getenv(c("RDOCS_A", "RDOCS_B", "RDOCS_C"), names = FALSE), c("from file", "quoted", "already set"))
})

test_that("set_env_value starts from .env.example, replaces a key, and appends a new one", {
  dir <- withr::local_tempdir()
  example <- file.path(dir, ".env.example")
  path <- file.path(dir, ".env")
  writeLines(c("# settings", "LOG_LEVEL=INFO"), example)
  withr::local_envvar(LOG_LEVEL = NA, RDOCS_LIBRARIES = NA)

  set_env_value("RDOCS_LIBRARIES", "/a:/b", path, example)
  set_env_value("LOG_LEVEL", "DEBUG", path, example)

  expect_equal(readLines(path), c("# settings", 'LOG_LEVEL="DEBUG"', 'RDOCS_LIBRARIES="/a:/b"'))
  expect_equal(Sys.getenv("RDOCS_LIBRARIES"), "/a:/b")
})

test_that("the API address comes from RAG_URL, else the published port", {
  withr::local_envvar(RAG_URL = NA, RAG_HOST_PORT = NA)
  expect_equal(rag_url(), "http://localhost:8000")

  withr::local_envvar(RAG_HOST_PORT = "9000")
  expect_equal(rag_url(), "http://localhost:9000")

  withr::local_envvar(RAG_URL = "http://rag:8000")
  expect_equal(rag_url(), "http://rag:8000")
})

test_that("the client's origin is its computer, unless set (Docker mode: docker)", {
  withr::local_envvar(RDOCS_ORIGIN = NA)
  expect_equal(client_origin(), paste0("host:", Sys.info()[["nodename"]]))

  withr::local_envvar(RDOCS_ORIGIN = "docker")
  expect_equal(client_origin(), "docker")
})

test_that("chosen libraries come from RDOCS_LIBRARIES; a missing folder is skipped with a message", {
  existing <- normalize_library(withr::local_tempdir())
  missing <- file.path(existing, "deleted-project")
  withr::local_envvar(RDOCS_LIBRARIES = paste(existing, missing, existing, sep = .Platform$path.sep))

  expect_message(libraries <- selected_libraries(), "deleted-project")
  expect_equal(libraries, existing)
})

test_that("without RDOCS_LIBRARIES, the libraries are R's own", {
  withr::local_envvar(RDOCS_LIBRARIES = NA)

  expect_equal(selected_libraries(), unique(normalize_library(.libPaths())))
})
