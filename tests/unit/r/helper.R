# testthat runs helper*.R before the tests, with this folder as the working directory:
# load the code under test. Nothing here talks to the network.
for (file in c("config.R", "extract.R", "api.R", "setup.R")) {
  source(file.path("..", "..", "..", "src", "client", file))
}

# A small package that every R installation has, in the library of the R running the tests.
PKG <- "compiler"
LIB <- .Library
