#!/usr/bin/env bash
# make-deb.sh <deb-arch>
# Wraps dist/img2 (produced by PyInstaller --onefile) into a .deb.
# Run from the repo root after pyinstaller packaging/img2.spec completes.
set -euo pipefail

DEB_ARCH=${1:?Usage: make-deb.sh <deb-arch>   (e.g. amd64 or arm64)}
BINARY=dist/img2

if [[ ! -f "${BINARY}" ]]; then
  echo "Error: ${BINARY} not found. Run pyinstaller first." >&2
  exit 1
fi

VERSION=$(python3 - <<'PY'
import tomllib, pathlib
d = tomllib.load(pathlib.Path("pyproject.toml").open("rb"))
print(d["project"]["version"])
PY
)

PKG_NAME="img2_${VERSION}_${DEB_ARCH}"
PKG_DIR="dist/deb/${PKG_NAME}"

rm -rf "${PKG_DIR}"
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/local/bin"

install -m 755 "${BINARY}" "${PKG_DIR}/usr/local/bin/img2"

cat > "${PKG_DIR}/DEBIAN/control" <<CONTROL
Package: img2
Version: ${VERSION}
Architecture: ${DEB_ARCH}
Maintainer: Brian Blankenship <briandb1222@gmail.com>
Description: Convert images to colored ASCII or traditional ANSI art
 img2 converts raster images into ASCII art (PNG/HTML output) or
 ANSI block-art (.ans and PNG output). Self-contained binary; no
 Python or system cairo installation required.
CONTROL

dpkg-deb --build --root-owner-group "${PKG_DIR}" "dist/${PKG_NAME}.deb"
echo "Built: dist/${PKG_NAME}.deb"
