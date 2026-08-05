"""Chunked file I/O helpers for large geospatial uploads and downloads."""

from collections.abc import Iterator
from pathlib import Path

DEFAULT_CHUNK_SIZE = 1024 * 1024


def stream_large_file(
    filepath: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[bytes]:
    """Yield a file as bounded binary chunks without loading it all at once."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    with Path(filepath).open("rb") as source:
        while chunk := source.read(chunk_size):
            yield chunk
