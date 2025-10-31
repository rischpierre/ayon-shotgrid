# Package selector for ShotGrid helpers
# Usage: import the helpers from whiteboard.sg_helpers and switch implementation via env var
# Env var: WHITEBOARD_SG_MODE = "real" (default) or "mock"/"test"

from __future__ import annotations

import os

dev_mode = os.getenv("WHITEBOARD_SG_DEV_MODE", False)

if dev_mode:
    print("Using mocked ShotGrid implementation")
    from .mocked import *  # type: ignore  # noqa: F401,F403
else:
    print("Using real ShotGrid implementation")
    from .real import *  # type: ignore  # noqa: F401,F403
