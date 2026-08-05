"""GeoFile Toolkit command-line interface."""

import click

from cli import __version__


@click.group()
@click.version_option(version=__version__, prog_name="geofile")
def geofile() -> None:
    """Parse, convert, validate, repair, and analyze geospatial files."""


if __name__ == "__main__":
    geofile()
