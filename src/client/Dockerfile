# The R client in a container (docker-compose.yml): Docker mode (r-extract: sync and install
# without R on your computer) and the R tests (r-test). In host mode the same code runs in
# your own R instead: docs/setup.md.
FROM rocker/r-ver:4.5.1

# httr2: HTTP client (JSON bodies, retries, readable errors); testthat: the R tests
# (make test-r). rocker images install from a dated CRAN snapshot, so this (and
# `make install`) gives the same versions on every build.
RUN install2.r --error httr2 testthat

# The Docker library (volume r_docker_lib): packages installed with `make install`.
RUN mkdir -p /libraries/docker
