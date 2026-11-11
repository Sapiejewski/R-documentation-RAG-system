# init and doctor (setup.R): the questions, the checks and their fixes. Nothing here starts
# Docker or installs anything: checks with side effects are replaced by fake ones.

# Prepared answers for ask(), as if typed in the terminal (STDIN is where ask() reads).
answers <- function(...) assign("STDIN", textConnection(as.character(c(...))), envir = globalenv())

test_that("a choice of numbers picks those libraries; Enter picks all; nonsense is ignored", {
  expect_equal(parse_choice("", 3), 1:3)
  expect_equal(parse_choice(NA_character_, 3), 1:3)
  expect_equal(parse_choice("1 3", 3), c(1, 3))
  expect_equal(parse_choice("2, 2,9 x", 3), 2)
})

test_that("yes/no questions take the default on Enter", {
  answers("", "n", "tak")
  expect_output(expect_true(ask_yes_no("Fix?")))
  expect_output(expect_false(ask_yes_no("Fix?")))
  expect_output(expect_true(ask_yes_no("Fix?", default = FALSE)))
})

test_that("with nobody to answer (no terminal), a yes/no question is always no", {
  answers() # no answers at all
  expect_output(expect_false(ask_yes_no("Install it?", default = TRUE)), "no answer")
})

test_that("a failed check's fix is offered, applied when accepted, and checked again", {
  state <- new.env()
  state$fixed <- FALSE
  checks <- list(thing = function() {
    if (state$fixed) return(check_result(TRUE, "there"))
    check_result(FALSE, "missing", hint = "get the thing", fix = function() state$fixed <- TRUE)
  })

  answers("y")
  expect_output(ok <- run_checks("thing", fix = TRUE, checks = checks), "OK    thing      there")
  expect_true(ok)
  expect_true(state$fixed)
})

test_that("a declined fix is not applied; the hint says what to do", {
  state <- new.env()
  state$fixed <- FALSE
  checks <- list(thing = function() check_result(FALSE, "missing", hint = "get the thing", fix = function() state$fixed <- TRUE))

  answers("n")
  expect_output(ok <- run_checks("thing", fix = TRUE, checks = checks), "-> get the thing")
  expect_false(ok)
  expect_false(state$fixed)
})

test_that("doctor only reports: no fix is offered", {
  checks <- list(thing = function() check_result(FALSE, "missing", fix = function() stop("must not run")))

  expect_output(expect_false(run_checks("thing", checks = checks)), "FAIL  thing")
})

test_that("the R version check passes on the R running the tests", {
  expect_true(check_r()$ok)
})

test_that("the libraries check lists each library with its package count", {
  withr::local_envvar(RDOCS_LIBRARIES = LIB)
  result <- check_libraries()
  expect_true(result$ok)
  expect_match(result$detail, "RDOCS_LIBRARIES in .env")
  expect_match(result$detail, paste0(normalize_library(LIB), "  \\(\\d+ packages\\)"))

  withr::local_envvar(RDOCS_LIBRARIES = file.path(tempdir(), "nothing-here"))
  result <- suppressMessages(check_libraries())
  expect_false(result$ok)
  expect_match(result$hint, "init")
})

test_that("init's library question saves the choice in .env", {
  withr::local_dir(withr::local_tempdir())
  withr::local_envvar(RDOCS_LIBRARIES = NA)
  extra <- normalize_library(withr::local_tempdir())
  first <- unique(normalize_library(.libPaths()))[1]

  answers("1", extra, "") # library 1, plus one more folder, then done
  expect_output(choose_libraries(), "Saved in .env")

  expected <- paste(c(first, extra), collapse = .Platform$path.sep)
  expect_equal(readLines(".env"), paste0('RDOCS_LIBRARIES="', expected, '"'))
})

test_that("hints name the command for this system", {
  expect_equal(command_for("init"), if (.Platform$OS.type == "windows") ".\\init.ps1" else "make init")
})
