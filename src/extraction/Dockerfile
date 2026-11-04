# R toolchain for the r-extract service (docker-compose.yml): reads the help pages
# of installed R packages and writes them as JSON Lines.
FROM rocker/r-ver:4.5.1

# The only R package the extraction scripts need. rocker images install from a dated
# CRAN snapshot, so this (and `make ingest`) gives the same versions on every build.
RUN install2.r --error jsonlite

# Docker-only library for experiments (volume r_docker_lib). Owned by the host user the
# container runs as, so it can install there and its output files are not owned by root.
ARG HOST_UID=1000
RUN mkdir -p /libraries/docker && chown "${HOST_UID}" /libraries/docker
