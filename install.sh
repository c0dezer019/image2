#!/usr/bin/env bash
# install.sh — install `ascii` command system-wide via pipx (no venv activation needed)
#
# Usage: ./install.sh [--editable]
#   --editable   install in editable mode (changes to source take effect immediately)
#
# Assumes: bash, Linux/macOS, Homebrew present (or pipx already installed).
# Installs pipx via brew if missing, then pipx-installs this project.
# pipx puts the `ascii` binary on PATH (~/.local/bin) in its own isolated venv —
# no manual venv activation ever needed afterward.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
EDITABLE=0

for arg in "$@"; do
    case "$arg" in
        --editable|-e) EDITABLE=1 ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "error: unknown argument '$arg' (try --help)" >&2
            exit 1
            ;;
    esac
done

# --- sanity checks -----------------------------------------------------------

if [[ ! -f "$SCRIPT_DIR/pyproject.toml" ]]; then
    echo "error: pyproject.toml not found in $SCRIPT_DIR — run this from the project root." >&2
    exit 1
fi

# --- ensure pipx is available -------------------------------------------------

if ! command -v pipx &>/dev/null; then
    echo "pipx not found — attempting to install it..."
    if command -v brew &>/dev/null; then
        brew install pipx
    elif command -v python3 &>/dev/null; then
        # Fall back to pip --user; --break-system-packages needed on externally
        # managed interpreters (PEP 668), harmless on others.
        python3 -m pip install --user pipx --break-system-packages 2>/dev/null \
            || python3 -m pip install --user pipx
    else
        echo "error: neither brew nor python3 available — install pipx manually: https://pipx.pypa.io/" >&2
        exit 1
    fi
fi

# pipx needs its bin dir on PATH for the installed app to be runnable directly.
if command -v pipx &>/dev/null; then
    pipx ensurepath &>/dev/null || true
else
    echo "error: pipx still not on PATH after install attempt. Open a new shell and re-run, or install pipx manually." >&2
    exit 1
fi

# --- install the project -------------------------------------------------------

echo "Installing 'ascii' command from $SCRIPT_DIR ..."
if [[ "$EDITABLE" -eq 1 ]]; then
    pipx install --force --editable "${SCRIPT_DIR}[png]"
else
    pipx install --force "${SCRIPT_DIR}[png]"
fi

echo
if command -v ascii &>/dev/null; then
    echo "Done. 'ascii' is on PATH: $(command -v ascii)"
    ascii --help 2>/dev/null | head -n 1 || true
else
    echo "Installed, but 'ascii' isn't on PATH yet in this shell."
    echo "Run:  source ~/.bashrc   (or open a new terminal)   then try: ascii --help"
fi
