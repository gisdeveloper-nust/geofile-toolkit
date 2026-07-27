"""Cleanup helpers for temporary upload and conversion files."""

import shutil
from pathlib import Path


def cleanup_temp_files(path: str | Path) -> None:
    """Remove a temporary file or directory if it still exists."""
    target = Path(path)
    if not target.exists():
        return
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
    else:
        target.unlink(missing_ok=True)
