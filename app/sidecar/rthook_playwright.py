"""PyInstaller runtime hook: restore execute permissions on Playwright driver binaries.

macOS app bundles / DMG packaging strip execute bits from binaries collected as
DATA by PyInstaller's ``collect_data_files``.  This hook runs before any
application code, ensuring ``playwright/driver/node`` is executable before
Playwright tries to spawn it.
"""

import os
import stat
import sys

_MEIPASS = getattr(sys, "_MEIPASS", None)

if _MEIPASS is not None:
    _EXECUTABLES = (
        os.path.join(_MEIPASS, "playwright", "driver", "node"),
        os.path.join(_MEIPASS, "playwright", "driver", "package", "cli.js"),
    )
    for _path in _EXECUTABLES:
        if os.path.exists(_path) and not os.access(_path, os.X_OK):
            try:
                _st = os.stat(_path).st_mode
                os.chmod(_path, _st | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass
