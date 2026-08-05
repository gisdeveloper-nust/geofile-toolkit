"""GeoFile Toolkit command-line interface."""

from pathlib import Path

import click

from cli import __version__
from app.converters.base_converter import load_any
from app.converters.format_converter import convert
from app.parsers.csv_parser import parse_csv
from app.parsers.geojson_parser import parse_geojson
from app.parsers.gpx_parser import parse_gpx
from app.parsers.kml_parser import parse_kml
from app.parsers.shapefile_parser import parse_shapefile
from app.repairs.geometry_repair import repair_batch
from app.validators.geometry_validator import detect_geometry_issues


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


def _format_from_path(path: Path) -> str:
    formats = {
        ".shp": "shapefile",
        ".geojson": "geojson",
        ".json": "geojson",
        ".kml": "kml",
        ".gpx": "gpx",
        ".csv": "csv",
    }
    target_format = formats.get(path.suffix.lower())
    if target_format is None:
        raise click.ClickException(
            f"Unsupported output format '{path.suffix or '(none)'}'"
        )
    return target_format


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


@geofile.command("convert")
@click.argument(
    "input_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.argument(
    "output_file",
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option("--crs", "target_crs", help="Optional target CRS, such as EPSG:3857.")
def convert_command(
    input_file: Path,
    output_file: Path,
    target_crs: str | None,
) -> None:
    """Convert INPUT_FILE to the format implied by OUTPUT_FILE."""
    try:
        frame = load_any(str(input_file))
        target_format = _format_from_path(output_file)
        converted_path = convert(
            frame,
            target_format,
            str(output_file),
            target_crs=target_crs,
        )
    except click.ClickException:
        raise
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Converted file: {converted_path}")


@geofile.command("validate")
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def validate_command(file: Path) -> None:
    """Validate every geometry in FILE and print detected issues."""
    try:
        frame = load_any(str(file))
        issues = detect_geometry_issues(frame)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not issues:
        click.echo("No issues found.")
        return

    click.echo(f"Found {len(issues)} geometry issue(s):")
    for issue in issues:
        click.echo(
            f"- Feature {issue['feature_index']}: "
            f"{issue['issue_type']} - {issue['description']}"
        )


@geofile.command("repair")
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output path; defaults to <name>_repaired.<format>.",
)
def repair_command(file: Path, output: Path | None) -> None:
    """Repair invalid geometries in FILE and write the repaired layer."""
    output_path = output or file.with_name(f"{file.stem}_repaired{file.suffix}")
    try:
        frame = load_any(str(file))
        repaired_frame, report = repair_batch(frame)
        target_format = _format_from_path(output_path)
        converted_path = convert(
            repaired_frame,
            target_format,
            str(output_path),
        )
    except click.ClickException:
        raise
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    fixed_count = sum(item["status"] == "fixed" for item in report)
    unfixable_count = sum(item["status"] == "unfixable" for item in report)
    click.echo(f"Fixed: {fixed_count}")
    click.echo(f"Unfixable: {unfixable_count}")
    click.echo(f"Repaired file: {converted_path}")


if __name__ == "__main__":
    geofile()
