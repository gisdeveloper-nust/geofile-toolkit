"""GeoFile Toolkit command-line interface."""

from pathlib import Path

import click

from cli import __version__
from app.parsers.csv_parser import parse_csv
from app.parsers.geojson_parser import parse_geojson
from app.parsers.gpx_parser import parse_gpx
from app.parsers.kml_parser import parse_kml
from app.parsers.shapefile_parser import parse_shapefile


@click.group()
@click.version_option(version=__version__, prog_name="geofile")
def geofile() -> None:
    """Parse, convert, validate, repair, and analyze geospatial files."""


def _parse_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".shp":
        return parse_shapefile(str(path))
    if suffix in {".geojson", ".json"}:
        return parse_geojson(str(path))
    if suffix == ".kml":
        return parse_kml(str(path))
    if suffix == ".gpx":
        return parse_gpx(str(path))
    if suffix == ".csv":
        return parse_csv(str(path))
    raise click.ClickException(
        f"Unsupported file format '{suffix or '(none)'}'"
    )


@geofile.command("parse")
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def parse_command(file: Path) -> None:
    """Parse FILE and print a concise spatial metadata summary."""
    try:
        result = _parse_file(file)
    except click.ClickException:
        raise
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Geometry: {result['geometry_type']}")
    click.echo(f"Features: {result['feature_count']}")
    click.echo(f"CRS: {result['crs'] or 'Not defined'}")
    click.echo(f"Bounding box: {result['bounding_box']}")
    if "layer_counts" in result:
        layers = ", ".join(
            f"{name}={count}"
            for name, count in result["layer_counts"].items()
        )
        click.echo(f"Layers: {layers}")


if __name__ == "__main__":
    geofile()
