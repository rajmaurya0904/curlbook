"""Read a collection file from disk, choosing the parser by extension."""

from __future__ import annotations

from pathlib import Path

from .errors import CurlbookError, ParseError
from .http_parser import parse_http_document
from .model import Collection
from .yaml_parser import parse_yaml_document

HTTP_SUFFIXES = (".http", ".rest")
YAML_SUFFIXES = (".yaml", ".yml")


class CollectionNotFound(CurlbookError):
    """The collection path does not exist or cannot be read."""


def load_collection(path: str | Path) -> Collection:
    """Parse a ``.http``/``.rest`` or ``.yaml``/``.yml`` file.

    Raises :class:`CollectionNotFound` for a missing file and :class:`ParseError`
    (with file and line) for bad content.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".json":
        raise ParseError(
            f"{p} is JSON; if it is a Postman collection run: curlbook import {p} -o out.http"
        )
    if suffix not in HTTP_SUFFIXES + YAML_SUFFIXES:
        raise ParseError(f"{p}: unsupported file type {suffix or '(none)'!r}; use .http or .yaml")
    try:
        text = p.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise CollectionNotFound(f"file not found: {p}") from None
    except IsADirectoryError:
        raise CollectionNotFound(f"{p} is a directory, not a collection file") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise CollectionNotFound(f"cannot read {p}: {exc}") from None
    if suffix in YAML_SUFFIXES:
        return parse_yaml_document(text, source=str(p))
    return parse_http_document(text, source=str(p))


def expand_paths(paths: list[str]) -> list[Path]:
    """Files as given; a directory expands to its ``.http``/``.rest``/``.yaml`` files, sorted."""
    out: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found = sorted(
                f for f in p.rglob("*") if f.suffix.lower() in HTTP_SUFFIXES + YAML_SUFFIXES
            )
            if not found:
                raise CollectionNotFound(f"no .http or .yaml files in {p}")
            out.extend(found)
        else:
            out.append(p)
    return out
