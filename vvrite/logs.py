"""File logging for the packaged app.

An .app launched from Finder has stdout and stderr wired to /dev/null, so every
print() in the transcription path vanished — including the ones that say why a
correction was skipped. That made "is this even working?" unanswerable without
rebuilding. Log to a file instead, where `tail -f` can reach it.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_PATH = os.path.expanduser("~/Library/Logs/vvrite.log")


def setup():
    """Attach a rotating file handler to the root logger. Safe to call twice."""
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        # A dictation logs a few short lines, so 1 MB holds weeks of history.
        handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=1)
    except OSError:
        return  # a read-only home is not worth crashing the app over
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%m-%d %H:%M:%S"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)


log = logging.getLogger("vvrite")
