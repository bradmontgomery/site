"""A simple static site generator."""

from importlib.metadata import version, PackageNotFoundError
from sitebuilder.cli import cli

try:
    __version__ = version("site")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["cli"]
