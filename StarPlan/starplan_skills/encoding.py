"""Windows-safe text stream configuration for StarPlan command-line tools."""

from __future__ import annotations

import io
import os
import sys


def configure_utf8_stdio() -> None:
    """Use UTF-8 for console and pipe text without replacing test capture streams.

    Python's Windows default may be GBK even when the repository and JSON files
    are UTF-8. ``reconfigure`` changes only real text wrappers; pytest and other
    capture objects that do not expose it are left untouched.
    """

    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(
                encoding="utf-8",
                errors="strict" if stream_name == "stdin" else "replace",
            )
        except (AttributeError, io.UnsupportedOperation, OSError, ValueError):
            # Embedded interpreters and test capture wrappers can reject this.
            continue

    # Child Python processes inherit this value; it has no effect on the
    # already-started interpreter and is therefore safe to set here as well.
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


__all__ = ["configure_utf8_stdio"]
