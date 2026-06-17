# img2.spec — PyInstaller spec for img2 (cross-platform, onefile)
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

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
    ),
    hiddenimports=(
        collect_submodules("cairosvg")
        + collect_submodules("cairocffi")
        + [
            "img2ansi",
            "img2ascii",
            "imgcommon",
            "imgsvg",
            "PIL",
            "PIL.Image",
            "PIL.ImageFilter",
            "PIL.ImageOps",
            "PIL.ImageEnhance",
            "PIL.ImageStat",
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
