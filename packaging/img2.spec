# img2.spec — PyInstaller spec for img2 (cross-platform, onefile)
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

block_cipher = None

# SPECPATH is the directory containing this spec file (packaging/).
root = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(root, "image2.py")],
    pathex=[root],
    binaries=[],
    datas=(
        collect_data_files("cairosvg")
        + collect_data_files("cairocffi")
        + collect_data_files("PIL")
        + copy_metadata("image2")
        + [(os.path.join(root, "_img2ui_data", "docker-compose.yml"), "_img2ui_data")]
    ),
    hiddenimports=(
        collect_submodules("cairosvg")
        + collect_submodules("cairocffi")
        + collect_submodules("PIL")
        + [
            "img2ansi",
            "img2ascii",
            "imgcommon",
            "imgsvg",
            "img2ui",
            "_img2ui_data",
        ]
    ),
    hookspath=[os.path.join(SPECPATH, "hooks")],
    hooksconfig={},
    runtime_hooks=[
        os.path.join(SPECPATH, "hooks", "rthook-cairocffi.py")
    ],
    excludes=["tkinter", "unittest", "test"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Exclude bundled libstdc++/libgcc — they're older than what system Qt6/ICU
# requires, causing GLIBCXX_3.4.32 / CXXABI_1.3.15 not found at runtime.
a.binaries = [
    x for x in a.binaries
    if not any(x[0].startswith(lib) for lib in ("libstdc++", "libgcc_s"))
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="img2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
