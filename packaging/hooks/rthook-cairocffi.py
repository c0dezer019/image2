# Runtime hook: make cairocffi find the bundled libcairo.
# In onefile mode, PyInstaller extracts binaries to sys._MEIPASS.
# cairocffi uses ctypes to dlopen libcairo, which won't search _MEIPASS
# by default on Linux. Prepend it to LD_LIBRARY_PATH before any import.
import os
import sys

if hasattr(sys, "_MEIPASS") and sys.platform.startswith("linux"):
    _existing = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = (
        sys._MEIPASS + (os.pathsep + _existing if _existing else "")
    )
