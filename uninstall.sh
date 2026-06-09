#!/usr/bin/env bash
# uninstall.sh — remove `img2` (pico-ascii) installed via pipx
#
# Usage: ./uninstall.sh [--yes]
#   --yes   skip confirmation prompt
#
# Only removes the pipx-managed install. Does not touch source files.

set -euo pipefail

PKG="image2"
CMD="img2"
YES=0

for arg in "$@"; do
    case "$arg" in
        --yes|-y) YES=1 ;;
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

# --- check pipx available -----------------------------------------------------

if ! command -v pipx &>/dev/null; then
    echo "error: pipx not found — nothing to uninstall." >&2
    exit 1
fi

# --- check actually installed -------------------------------------------------

if ! pipx list --short 2>/dev/null | grep -q "^${PKG} "; then
    echo "'${PKG}' is not installed via pipx — nothing to do."
    exit 0
fi

# Show what will be removed
INSTALLED_PATH="$(command -v "$CMD" 2>/dev/null || echo '(not on PATH)')"
echo "Will remove: ${PKG}"
echo "  Binary:    ${INSTALLED_PATH}"

# --- confirm ------------------------------------------------------------------

if [[ "$YES" -eq 0 ]]; then
    read -r -p "Proceed? [y/N] " REPLY
    case "$REPLY" in
        [yY][eE][sS]|[yY]) ;;
        *)
            echo "Aborted."
            exit 0
            ;;
    esac
fi

# --- uninstall ----------------------------------------------------------------

pipx uninstall "${PKG}"

# Verify gone
if command -v "$CMD" &>/dev/null; then
    echo "warning: '${CMD}' still found at $(command -v "$CMD") — may be a separate install." >&2
else
    echo "Done. '${CMD}' removed."
fi
