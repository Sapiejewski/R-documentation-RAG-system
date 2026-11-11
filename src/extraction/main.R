#!/usr/bin/env Rscript
# Entry point of the r-extract container (docker-compose.yml). Usually run through make:
#
#   Rscript main.R sync              # make sync:   extract new/changed packages of every
#                                    #              library mounted under /libraries
#   Rscript main.R install <pkg>...  # make install: install into the Docker-only library
#
# Libraries are mounted by docker-compose.yml: /libraries/system and /libraries/user
# (host folders, read-only) and /libraries/docker (volume, for experiments).

script <- sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE))
source(file.path(dirname(script), "extract.R"))

args <- commandArgs(trailingOnly = TRUE)
command <- if (length(args) > 0) args[[1]] else ""

switch(command,
  sync = sync_libraries(),
  install = install_packages(args[-1]),
  stop("usage: main.R sync | main.R install <package>...")
)
