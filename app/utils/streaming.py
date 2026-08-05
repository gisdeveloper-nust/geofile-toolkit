"""Chunked file I/O helpers for large geospatial uploads and downloads."""

from collections.abc import Iterator
import os
from pathlib import Path

from fastapi import UploadFile

DEFAULT_CHUNK_SIZE = 1024 * 1024
STREAMING_THRESHOLD_BYTES = int(
    os.environ.get("GEOFILE_STREAMING_THRESHOLD_BYTES", 8 * 1024 * 1024)
)
MAX_UPLOAD_BYTES = int(
    os.environ.get("GEOFILE_MAX_UPLOAD_BYTES", 100 * 1024 * 1024)
)


class FileSizeLimitExceeded(ValueError):
    """Raised when an upload exceeds the configured maximum size."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        super().__init__(f"File exceeds maximum upload size of {max_bytes} bytes")


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
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> int:
    """Save an upload, switching to chunked writes above ``threshold``."""
    destination_path = Path(destination)
    size_hint = upload.size
    if size_hint is not None and size_hint > max_bytes:
        raise FileSizeLimitExceeded(max_bytes)
    if size_hint is not None and size_hint <= threshold:
        content = await upload.read()
        if len(content) > max_bytes:
            raise FileSizeLimitExceeded(max_bytes)
        destination_path.write_bytes(content)
        return len(content)

    total_bytes = 0
    with destination_path.open("wb") as target:
        while chunk := await upload.read(chunk_size):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                target.close()
                destination_path.unlink(missing_ok=True)
                raise FileSizeLimitExceeded(max_bytes)
            target.write(chunk)
    return total_bytes
