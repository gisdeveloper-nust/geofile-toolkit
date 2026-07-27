"""GeoFile Toolkit application entry point."""

from fastapi import FastAPI

app = FastAPI(title="GeoFile Toolkit")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Report whether the API process is healthy."""
    return {"status": "healthy"}
