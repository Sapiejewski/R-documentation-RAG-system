#!/usr/bin/env Rscript
# Entry point of the R client. Runs on your computer (host mode) or in the r-extract
# container (Docker mode). Usually through make, or the init scripts:
#
#   Rscript src/client/main.R init       first setup: checks, fixes (asking first), choose libraries
#   Rscript src/client/main.R doctor     check everything, with a hint for each problem
#   Rscript src/client/main.R sync       index new and changed packages of the chosen libraries
#   Rscript src/client/main.R install <pkg>...   Docker mode only: install into the Docker library
#
# The flow on Linux, macOS and Windows: docs/setup.md.

script <- sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE))
client_dir <- dirname(normalizePath(script))
for (file in c("config.R", "extract.R", "api.R", "setup.R")) source(file.path(client_dir, file))

# Work from the repository root, where .env and docker-compose.yml are.
setwd(dirname(dirname(client_dir)))
load_env_file()
STDIN <- file("stdin") # Rscript: answers to init's questions come from the terminal
open(STDIN)

args <- commandArgs(trailingOnly = TRUE)
command <- if (length(args) > 0) args[[1]] else ""

switch(command,
  init = init(),
  doctor = if (!doctor()) quit(status = 1),
  sync = sync_libraries(selected_libraries()),
  install = install_packages(args[-1]),
  stop("usage: main.R init | doctor | sync | install <package>...")
)
