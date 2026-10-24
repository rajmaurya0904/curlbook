"""Load variables from ``.json``, ``.yaml``/``.yml`` or ``.env`` files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .errors import EnvError

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")


def parse_dotenv(text: str, source: str = ".env") -> dict[str, str]:
    """Parse ``KEY=value`` lines. Supports comments, ``export``, and quoted values."""
    out: dict[str, str] = {}
    for no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, eq, value = line.partition("=")
        key = key.strip()
        if not eq or not _KEY.match(key):
            raise EnvError(f"{source}:{no}: expected KEY=value, got {raw.strip()!r}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            quote = value[0]
            value = value[1:-1]
            if quote == '"':
                value = value.replace("\\n", "\n").replace('\\"', '"')
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        out[key] = value
    return out


def load_env(path: str | Path) -> dict[str, Any]:
    """Read an environment file; the format follows the extension.

    ``.json`` and ``.yaml`` files must hold a mapping at the top level. Any other name
    (``.env``, ``prod.env``, ``.env.local``) is read as dotenv.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise EnvError(f"environment file not found: {p}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise EnvError(f"cannot read environment file {p}: {exc}") from None

    suffix = p.suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise EnvError(f"{p}: invalid JSON: {exc}") from None
    elif suffix in (".yaml", ".yml"):
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise EnvError(f"{p}: invalid YAML: {exc}") from None
    else:
        return dict(parse_dotenv(text, str(p)))

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise EnvError(f"{p}: expected a mapping of variable names to values")
    return {str(k): v for k, v in data.items()}


def parse_assignments(items: list[str] | tuple[str, ...]) -> dict[str, str]:
    """Turn ``["a=1", "b=two"]`` (from repeated ``--var``) into a dict."""
    out: dict[str, str] = {}
    for item in items:
        key, eq, value = item.partition("=")
        if not eq or not key.strip():
            raise EnvError(f"--var expects NAME=VALUE, got {item!r}")
        out[key.strip()] = value
    return out
