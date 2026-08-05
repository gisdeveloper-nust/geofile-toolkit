"""Chunked file I/O helpers for large geospatial uploads and downloads."""

from collections.abc import Iterator
import os
from pathlib import Path

from fastapi import UploadFile

DEFAULT_CHUNK_SIZE = 1024 * 1024
STREAMING_THRESHOLD_BYTES = int(
    os.environ.get("GEOFILE_STREAMING_THRESHOLD_BYTES", 8 * 1024 * 1024)
)


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


async def save_upload_file(
    upload: UploadFile,
    destination: str | Path,
    threshold: int = STREAMING_THRESHOLD_BYTES,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> int:
    """Save an upload, switching to chunked writes above ``threshold``."""
    destination_path = Path(destination)
    size_hint = upload.size
    if size_hint is not None and size_hint <= threshold:
        content = await upload.read()
        destination_path.write_bytes(content)
        return len(content)

    total_bytes = 0
    with destination_path.open("wb") as target:
        while chunk := await upload.read(chunk_size):
            target.write(chunk)
            total_bytes += len(chunk)
    return total_bytes
