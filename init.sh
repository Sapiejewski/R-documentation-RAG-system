#!/bin/sh
# First setup on Linux and macOS (`make init` runs this; Windows: init.ps1).
#
# This script only makes sure R is there -- offering to install it, never without asking.
# Everything else (httr2, Docker, which R libraries to index, starting the services) is
# done in R by src/client/setup.R, the same on every system. Flow: docs/setup.md.
set -e
cd "$(dirname "$0")"

# The command that installs R on this system, or nothing if we do not know one.
install_command() {
    case "$(uname -s)" in
        Darwin) command -v brew >/dev/null 2>&1 && echo "brew install --cask r" ;;
        Linux)
            if command -v apt-get >/dev/null 2>&1; then echo "sudo apt-get install -y r-base"
            elif command -v dnf >/dev/null 2>&1; then echo "sudo dnf install -y R"
            fi ;;
    esac
}

if ! command -v Rscript >/dev/null 2>&1; then
    echo "R was not found (no Rscript on PATH)."
    cmd="$(install_command)"
    answer=""
    if [ -n "$cmd" ]; then
        printf "Install it now with:  %s  ? [y/N] " "$cmd"
        read -r answer || answer=""
    fi
    case "$answer" in
        y|Y|yes|t|tak) sh -c "$cmd" ;;
        *)
            echo "Install R from https://cloud.r-project.org and run this again."
            echo "Without R you can still use Docker mode: make up, then make install / make sync-docker."
            exit 1 ;;
    esac
    if ! command -v Rscript >/dev/null 2>&1; then
        echo "R is installed, but this terminal does not see it yet: open a new terminal and run this again."
        exit 1
    fi
fi

exec Rscript src/client/main.R init
