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
mkdir -p "${PKG_DIR}/usr/share/metainfo"
mkdir -p "${PKG_DIR}/usr/share/doc/img2"

install -m 755 "${BINARY}" "${PKG_DIR}/usr/local/bin/img2"
install -m 644 packaging/io.github.c0dezer019.img2.metainfo.xml \
  "${PKG_DIR}/usr/share/metainfo/io.github.c0dezer019.img2.metainfo.xml"

cat > "${PKG_DIR}/usr/share/doc/img2/copyright" <<COPYRIGHT
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: img2
Source: https://github.com/c0dezer019/image2

Files: *
Copyright: $(date +%Y) Brian Blankenship
License: MIT

License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a
 copy of this software and associated documentation files (the
 "Software"), to deal in the Software without restriction, including
 without limitation the rights to use, copy, modify, merge, publish,
 distribute, sublicense, and/or sell copies of the Software, and to
 permit persons to whom the Software is furnished to do so, subject to
 the following conditions:
 .
 The above copyright notice and this permission notice shall be included
 in all copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
 OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
 ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 OTHER DEALINGS IN THE SOFTWARE.
COPYRIGHT

cat > "${PKG_DIR}/DEBIAN/control" <<CONTROL
Package: img2
Version: ${VERSION}
Architecture: ${DEB_ARCH}
Maintainer: Brian Blankenship <briandb1222@bblankenship.me>
Homepage: https://github.com/c0dezer019/image2
License: MIT
Description: Convert images to colored ASCII or traditional ANSI art
 img2 converts raster images into ASCII art (PNG/HTML output) or
 ANSI block-art (.ans and PNG output). Self-contained binary; no
 Python or system cairo installation required.
CONTROL

dpkg-deb --build --root-owner-group "${PKG_DIR}" "dist/${PKG_NAME}.deb"
echo "Built: dist/${PKG_NAME}.deb"
