#!/usr/bin/env bash
# install.sh — install or update `img2` command system-wide via pipx
#
# Usage: ./install.sh [--editable] [--update]
#   --editable   install in editable mode (source changes take effect immediately)
#   --update     reinstall from current source (picks up code/dep changes)
#
# Assumes: bash, Linux/macOS, Homebrew present (or pipx already installed).
# Installs pipx via brew if missing, then pipx-installs this project.
# pipx puts the `img2` binary on PATH (~/.local/bin) in its own isolated venv —
# no manual venv activation ever needed afterward.
#
# Update notes:
#   --update does a full uninstall + reinstall (not --force) so renamed/removed
#   entry points get pruned cleanly from ~/.local/bin. Use it whenever the
#   [project.scripts] section changes, not just for code edits.
#   pipx upgrade is NOT used — it pulls from PyPI, not local source.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
EDITABLE=0
UPDATE=0
PKG="image2"  # must match [project] name in pyproject.toml
CMD="img2"    # must match [project.scripts] in pyproject.toml

for arg in "$@"; do
    case "$arg" in
        --editable|-e) EDITABLE=1 ;;
        --update|-u)   UPDATE=1 ;;
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
    if [[ "$UPDATE" -eq 1 ]]; then
        echo "error: pipx not found — run install.sh (without --update) first." >&2
        exit 1
    fi
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

# --- detect whether already installed ----------------------------------------

ALREADY_INSTALLED=0
if pipx list --short 2>/dev/null | grep -q "^${PKG} "; then
    ALREADY_INSTALLED=1
fi

# Warn if --update requested but not installed
if [[ "$UPDATE" -eq 1 && "$ALREADY_INSTALLED" -eq 0 ]]; then
    echo "warning: '${PKG}' not currently installed via pipx — doing fresh install instead." >&2
fi

# --- install / reinstall the project -----------------------------------------

if [[ "$ALREADY_INSTALLED" -eq 1 && "$UPDATE" -eq 0 ]]; then
    echo "Note: '${PKG}' already installed. Use --update to reinstall/pick up changes."
    echo "      Current location: $(command -v "$CMD" 2>/dev/null || echo '(not on PATH)')"
    exit 0
fi

ACTION="Installing"
if [[ "$ALREADY_INSTALLED" -eq 1 ]]; then
    ACTION="Updating"
    # Full uninstall first — pipx install --force doesn't prune renamed/removed
    # entry points from ~/.local/bin, leaving dangling symlinks.
    echo "Removing old install of '${PKG}' before reinstall..."
    pipx uninstall "${PKG}"
fi

echo "${ACTION} '${CMD}' from ${SCRIPT_DIR} ..."
if [[ "$EDITABLE" -eq 1 ]]; then
    pipx install --editable "${SCRIPT_DIR}"
else
    pipx install "${SCRIPT_DIR}"
fi

echo
if command -v "$CMD" &>/dev/null; then
    echo "Done. '${CMD}' is on PATH: $(command -v "$CMD")"
    "$CMD" --help 2>/dev/null | head -n 1 || true
else
    echo "${ACTION} complete, but '${CMD}' isn't on PATH yet in this shell."
    echo "Run:  source ~/.bashrc   (or open a new terminal)   then try: ${CMD} --help"
fi
