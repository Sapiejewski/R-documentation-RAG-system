# Reading installed packages (extract.R), on a real base R package. No network.

test_that("the manifest lists installed packages with version and build stamp", {
  manifest <- library_manifest(LIB)

  expect_named(manifest, c("package", "version", "built"))
  row <- manifest[manifest$package == PKG, ]
  expect_equal(row$version, as.character(packageVersion(PKG, lib.loc = LIB)))
  expect_match(row$built, "^R ") # e.g. "R 4.5.1; ; 2025-06-13 ...; unix"
})

test_that("help pages have exactly the fields of the API's HelpPage schema", {
  pages <- help_pages(PKG, LIB)

  expect_gt(length(pages), 0)
  for (page in pages) {
    expect_named(page, c("name", "title", "aliases", "keywords", "text"))
    expect_true(nchar(page$text) > 0)
    expect_false("internal" %in% page$keywords)
  }
})

test_that("a help page is R's own text rendering", {
  pages <- help_pages(PKG, LIB)
  names <- vapply(pages, function(p) p$name, "")
  compile <- pages[[which(names == "compile")]]

  expect_true("cmpfun" %in% compile$aliases)
  expect_match(compile$text, "Usage:")
})

test_that("the package overview comes from DESCRIPTION", {
  overview <- package_overview(PKG, LIB)

  expect_equal(overview$title, "The R Compiler Package")
})

test_that("a library outside .libPaths() is read, and .libPaths() is left as it was", {
  # Pages that run R code while rendering load their own package, which R finds only on
  # .libPaths(): a chosen folder (e.g. a renv library) is usually not there.
  lib <- withr::local_tempdir()
  file.copy(file.path(LIB, PKG), lib, recursive = TRUE)
  before <- .libPaths()

  pages <- help_pages(PKG, lib)

  expect_gt(length(pages), 0)
  expect_equal(.libPaths(), before)
})
