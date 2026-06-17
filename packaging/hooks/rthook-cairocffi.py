# Runtime hook: make cairocffi find the bundled libcairo.
# In onefile mode, PyInstaller extracts binaries to sys._MEIPASS.
# cairocffi uses ctypes to dlopen libcairo, which won't search _MEIPASS
# by default on Linux/macOS. Prepend it to the appropriate path var.
import os
import sys

if hasattr(sys, "_MEIPASS"):
    if sys.platform.startswith("linux"):
        _var = "LD_LIBRARY_PATH"
    elif sys.platform == "darwin":
        _var = "DYLD_LIBRARY_PATH"
    else:
        _var = None
    if _var:
        _existing = os.environ.get(_var, "")
        os.environ[_var] = (
            sys._MEIPASS + (os.pathsep + _existing if _existing else "")
        )
