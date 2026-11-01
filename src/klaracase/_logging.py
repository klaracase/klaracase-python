"""Logging for the SDK.

The package logs to ``logging.getLogger("klaracase")``. It installs a ``NullHandler``, so it is
silent unless your application configures logging. Setting ``KLARACASE_LOG=info`` or
``KLARACASE_LOG=debug`` in the environment adds a stderr handler when the first client is built.

INFO: one line per request (method, path, status, attempt) and one per retry (with the wait).
DEBUG: the names of the query parameters of a request. WARNING: a deprecation.
Never logged: the token, a request body, a query value or a response body.
"""

from __future__ import annotations

import logging
import os
import sys

LOG_ENV_VAR = "KLARACASE_LOG"
LOGGER = logging.getLogger("klaracase")
LOGGER.addHandler(logging.NullHandler())

_LEVELS = {"info": logging.INFO, "debug": logging.DEBUG}
_MARK = "_klaracase_env_handler"


def setup_env_logging() -> None:
    """Install a stderr handler once when ``KLARACASE_LOG`` is ``info`` or ``debug``."""
    level = _LEVELS.get(os.environ.get(LOG_ENV_VAR, "").strip().lower())
    if level is None:
        return
    for handler in LOGGER.handlers:
        if getattr(handler, _MARK, False):
            handler.setLevel(level)
            LOGGER.setLevel(level)
            return
    handler = logging.StreamHandler(sys.stderr)
    setattr(handler, _MARK, True)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(level)
