# `init` and `doctor`: is everything the project needs in place? Sourced by main.R.
#
#   doctor  runs every check and prints it; a failed check also prints what to do.
#   init    the guided first setup: runs the checks, offers to fix what fails (asking first),
#           asks which R libraries to index and saves the answer in .env.
#
# Each check is a function returning check_result(ok, detail, hint, fix): `hint` tells the
# user what to do, `fix` (optional) does it. A new requirement = one new check in CHECKS,
# plus a row in the table of docs/setup.md, which also describes the flow on each system.

# --- talking to the user -------------------------------------------------------------------

# Where answers come from. main.R sets it to the terminal; tests set it to prepared answers.
STDIN <- stdin()

# Ask a question. The answer ("" for just Enter), or NA when nobody can answer (no terminal,
# e.g. init run from a script).
ask <- function(question) {
  cat(question)
  answer <- readLines(STDIN, n = 1)
  if (length(answer) == 0) {
    cat("(no answer)\n")
    return(NA_character_)
  }
  trimws(answer)
}

# Enter takes the default; with nobody to answer it is always "no": nothing is installed or
# started without a person agreeing.
ask_yes_no <- function(question, default = TRUE) {
  answer <- tolower(ask(paste0(question, if (default) " [Y/n] " else " [y/N] ")))
  if (is.na(answer)) return(FALSE)
  if (answer == "") default else answer %in% c("y", "yes", "t", "tak")
}

# The command for a step, as the user types it on this system (Windows usually has no make).
COMMANDS <- list(
  init = c(make = "make init", windows = ".\\init.ps1"),
  up = c(make = "make up", windows = ".\\init.ps1"),
  sync = c(make = "make sync", windows = "Rscript src/client/main.R sync")
)
command_for <- function(step) {
  COMMANDS[[step]][[if (.Platform$OS.type == "windows") "windows" else "make"]]
}

# --- the checks --------------------------------------------------------------------------------

check_result <- function(ok, detail, hint = "", fix = NULL) {
  list(ok = ok, detail = detail, hint = hint, fix = fix)
}

MIN_R_VERSION <- "4.1.0" # httr2 needs R 4.1

check_r <- function() {
  version <- paste(R.version$major, R.version$minor, sep = ".")
  if (package_version(version) >= MIN_R_VERSION) return(check_result(TRUE, version))
  check_result(FALSE, version, hint = paste0("R ", MIN_R_VERSION, " or newer is needed: https://cloud.r-project.org"))
}

check_httr2 <- function() {
  if (requireNamespace("httr2", quietly = TRUE)) {
    return(check_result(TRUE, as.character(utils::packageVersion("httr2"))))
  }
  check_result(FALSE, "not installed", hint = 'in R: install.packages("httr2")', fix = install_httr2)
}

# Install httr2 into the personal library (no admin rights needed). R creates that folder only
# when asked, so create it first.
install_httr2 <- function() {
  lib <- path.expand(strsplit(Sys.getenv("R_LIBS_USER"), .Platform$path.sep, fixed = TRUE)[[1]][1])
  dir.create(lib, recursive = TRUE, showWarnings = FALSE)
  .libPaths(c(lib, .libPaths()))
  utils::install.packages("httr2", lib = lib, repos = "https://cloud.r-project.org")
}

# The output of `docker <args>`, or NULL if docker is missing or the command failed.
run_docker <- function(args) {
  if (Sys.which("docker") == "") return(NULL)
  output <- suppressWarnings(system2("docker", args, stdout = TRUE, stderr = TRUE))
  if (!is.null(attr(output, "status"))) return(NULL)
  output
}

check_docker <- function() {
  if (Sys.which("docker") == "") {
    return(check_result(FALSE, "not installed",
                        hint = "install Docker: https://docs.docker.com/get-docker/ (Windows, macOS: Docker Desktop)"))
  }
  compose <- run_docker(c("compose", "version", "--short"))
  if (is.null(compose)) {
    return(check_result(FALSE, "Compose v2 missing", hint = "https://docs.docker.com/compose/install/"))
  }
  if (is.null(run_docker(c("info", "--format", "{{.ServerVersion}}")))) {
    return(check_result(FALSE, "installed, but not running (or no permission)",
                        hint = "start Docker Desktop (Linux: the docker service; your user in the docker group)"))
  }
  check_result(TRUE, paste("Compose", compose[[1]]))
}

# One line per library: its path and how many packages it holds.
describe_libraries <- function(libraries, numbered = FALSE) {
  counts <- vapply(libraries, function(lib) nrow(library_manifest(lib)), 0)
  labels <- if (numbered) paste0(seq_along(libraries), ". ") else ""
  sprintf("%s%s  (%d packages)", labels, libraries, counts)
}

check_libraries <- function() {
  libraries <- selected_libraries()
  if (length(libraries) == 0) {
    return(check_result(FALSE, "no R library to index", hint = paste("choose them:", command_for("init"))))
  }
  source <- if (Sys.getenv("RDOCS_LIBRARIES") == "") "R's .libPaths(), not chosen yet" else "RDOCS_LIBRARIES in .env"
  check_result(TRUE, paste(c(source, describe_libraries(libraries)), collapse = "\n"))
}

# Start the services and pull the models (what `make up` does).
start_services <- function() {
  docker_compose(c("up", "-d", "--wait", "--build", "qdrant", "ollama", "rag"))
  docker_compose(c("run", "--rm", "ollama-init"))
}

docker_compose <- function(args) {
  status <- system2("docker", c("compose", args)) # its output goes straight to the console
  if (status != 0) stop("docker compose ", paste(args, collapse = " "), " failed")
}

# The API's own report (GET /health), or NULL if it does not answer.
api_health <- function() {
  if (!requireNamespace("httr2", quietly = TRUE)) return(NULL)
  tryCatch(api_get("/health"), error = function(e) NULL)
}

check_api <- function() {
  if (!requireNamespace("httr2", quietly = TRUE)) return(check_result(FALSE, "not checked: needs httr2"))
  health <- api_health()
  if (is.null(health)) {
    return(check_result(FALSE, paste("no answer at", rag_url()),
                        hint = paste("start the services:", command_for("up")), fix = start_services))
  }
  check_result(TRUE, paste(rag_url(), "-", health$status))
}

check_services <- function() {
  if (!requireNamespace("httr2", quietly = TRUE)) return(check_result(FALSE, "not checked: needs httr2"))
  health <- api_health()
  if (is.null(health)) return(check_result(FALSE, "not checked: the API does not answer"))
  details <- vapply(health$services, function(s) paste0(s$name, ": ", s$detail), "")
  ok <- all(vapply(health$services, function(s) isTRUE(s$ok), TRUE))
  hint <- if (ok) "" else paste("start the services and pull the models:", command_for("up"))
  check_result(ok, paste(details, collapse = "\n"), hint = hint, fix = if (ok) NULL else start_services)
}

# Every check, in the order they depend on each other.
CHECKS <- list(
  R = check_r,
  httr2 = check_httr2,
  Docker = check_docker,
  libraries = check_libraries,
  API = check_api,
  services = check_services
)

# --- running them ------------------------------------------------------------------------

print_check <- function(name, result) {
  lines <- strsplit(result$detail, "\n", fixed = TRUE)[[1]]
  cat(sprintf("%-4s  %-10s %s\n", if (result$ok) "OK" else "FAIL", name, lines[1]))
  for (line in lines[-1]) cat(sprintf("%16s %s\n", "", line))
  if (!result$ok && result$hint != "") cat(sprintf("%16s -> %s\n", "", result$hint))
}

# Run the named checks and print them; with `fix`, offer the fix of each failed one first.
# TRUE if all of them pass. (`checks`: tests pass their own.)
run_checks <- function(names, fix = FALSE, checks = CHECKS) {
  all_ok <- TRUE
  for (name in names) {
    result <- checks[[name]]()
    if (!result$ok && fix && !is.null(result$fix)) {
      if (ask_yes_no(sprintf("%s: %s. Fix it now?", name, result$detail))) {
        result$fix()
        result <- checks[[name]]() # check again: did the fix work?
      }
    }
    print_check(name, result)
    all_ok <- all_ok && result$ok
  }
  all_ok
}

doctor <- function() {
  ok <- run_checks(names(CHECKS))
  cat(if (ok) "\nEverything is in place.\n" else "\nSome checks failed; each says what to do (docs/setup.md).\n")
  ok
}

# --- init ----------------------------------------------------------------------------------------

# "1 3" -> c(1, 3); "" (Enter) or NA (no answer) -> all of them. Numbers outside 1..n are ignored.
parse_choice <- function(answer, n) {
  if (is.na(answer) || answer == "") return(seq_len(n))
  numbers <- suppressWarnings(as.integer(strsplit(answer, "[ ,]+")[[1]]))
  unique(numbers[!is.na(numbers) & numbers >= 1 & numbers <= n])
}

# Ask which libraries to index and save them in .env (RDOCS_LIBRARIES).
choose_libraries <- function() {
  if (Sys.getenv("RDOCS_LIBRARIES") != "") {
    cat("Libraries to index (RDOCS_LIBRARIES in .env):\n")
    cat(paste0("  ", describe_libraries(selected_libraries()), "\n"), sep = "")
    if (!ask_yes_no("Change them?", default = FALSE)) return(invisible(NULL))
  }
  found <- unique(normalize_library(.libPaths()))
  cat("R libraries on this computer (.libPaths()):\n")
  cat(paste0("  ", describe_libraries(found, numbered = TRUE), "\n"), sep = "")
  chosen <- found[parse_choice(ask("Which to index? Numbers separated by spaces, Enter = all: "), length(found))]
  repeat {
    folder <- ask("Another folder to index (e.g. a project's renv library), Enter = done: ")
    if (is.na(folder) || folder == "") break
    folder <- normalize_library(folder)
    if (dir.exists(folder)) chosen <- c(chosen, folder) else cat("  no such folder:", folder, "\n")
  }
  if (length(chosen) == 0) {
    cat("Nothing chosen; using all of them.\n")
    chosen <- found
  }
  set_env_value("RDOCS_LIBRARIES", paste(unique(chosen), collapse = .Platform$path.sep))
  cat("Saved in .env as RDOCS_LIBRARIES (run init again to change it).\n\n")
}

init <- function() {
  cat("Checking what the project needs (docs/setup.md).\n\n")
  if (!run_checks(c("R", "httr2", "Docker"), fix = TRUE)) {
    stop("fix the problems above, then run ", command_for("init"), " again", call. = FALSE)
  }
  cat("\n")
  choose_libraries()
  if (!run_checks(c("libraries", "API", "services"), fix = TRUE)) {
    stop("fix the problems above, then run ", command_for("init"), " again", call. = FALSE)
  }
  cat("\nReady. Index your libraries:", command_for("sync"), "\n")
}
