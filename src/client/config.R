# Settings of the R client: environment variables and the repo's .env file (the same file
# Docker Compose and the Python service read). Sourced by main.R.

ENV_FILE <- ".env"
ENV_EXAMPLE <- ".env.example"

# KEY=VALUE lines of .env into the environment. A variable that is already set wins, so
# `RDOCS_LIBRARIES=... Rscript main.R sync` overrides .env (as in the Python service).
load_env_file <- function(path = ENV_FILE) {
  if (!file.exists(path)) return(invisible(NULL))
  for (line in trimws(readLines(path, warn = FALSE))) {
    if (line == "" || startsWith(line, "#") || !grepl("=", line, fixed = TRUE)) next
    key <- trimws(sub("=.*$", "", line))
    value <- gsub("^[\"']|[\"']$", "", trimws(sub("^[^=]*=", "", line)))
    if (Sys.getenv(key) == "") set_env(key, value)
  }
}

# Sys.setenv(KEY = value) for a key held in a variable.
set_env <- function(key, value) {
  args <- list(value)
  names(args) <- key
  do.call(Sys.setenv, args)
}

# Save KEY="value" in .env (replacing an existing KEY= line) and set it for this session.
# Without a .env yet, it starts from .env.example, so every documented setting is there.
set_env_value <- function(key, value, path = ENV_FILE, example = ENV_EXAMPLE) {
  if (!file.exists(path) && file.exists(example)) file.copy(example, path)
  lines <- if (file.exists(path)) readLines(path, warn = FALSE) else character(0)
  new_line <- paste0(key, '="', value, '"')
  existing <- grep(paste0("^", key, "="), lines)
  if (length(existing) > 0) {
    lines[existing[1]] <- new_line
  } else {
    lines <- c(lines, new_line)
  }
  writeLines(lines, path)
  set_env(key, value)
}

# Where the rag API answers. On the host: the port published by docker-compose.yml;
# inside Docker Compose, RAG_URL is set to http://rag:8000.
rag_url <- function() {
  Sys.getenv("RAG_URL", paste0("http://localhost:", Sys.getenv("RAG_HOST_PORT", "8000")))
}

# Absolute paths with "/" on every system, so the same folder is always the same library.
normalize_library <- function(paths) {
  normalizePath(path.expand(paths), winslash = "/", mustWork = FALSE)
}

# The R libraries to index, as absolute paths. A library is identified by its path.
#   RDOCS_LIBRARIES set (by `init`, in .env)  -> those folders, separated like R_LIBS:
#                                                 ":" on Linux/macOS, ";" on Windows
#   not set                                   -> R's own libraries, .libPaths()
# A folder that does not exist (any more) is skipped with a message.
selected_libraries <- function() {
  configured <- Sys.getenv("RDOCS_LIBRARIES")
  paths <- if (configured == "") .libPaths() else strsplit(configured, .Platform$path.sep, fixed = TRUE)[[1]]
  paths <- unique(normalize_library(paths[paths != ""]))
  for (path in paths[!dir.exists(paths)]) message("Skipping library ", path, ": the folder does not exist")
  paths[dir.exists(paths)]
}
