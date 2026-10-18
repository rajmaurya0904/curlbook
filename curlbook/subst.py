"""``{{ variable }}`` substitution for curlbook.

Three kinds of placeholder are understood:

* ``{{ name }}``: a variable from the environment dict. Names are letters,
  digits, ``_``, ``-`` and ``.`` and must not start with a digit.
* ``{{ $env.NAME }}``: a variable from the process environment, handy for CI secrets.
* ``{{ $uuid }}``, ``{{ $timestamp }}``, ``{{ $isoTimestamp }}``, ``{{ $randomInt }}``:
  values generated fresh at each use.

Anything else between double braces is left alone, so JSON such as
``{"a": {"b": 1}}`` passes through untouched.
"""

from __future__ import annotations

import os
import random
import re
import uuid
from datetime import UTC, datetime
from typing import Any

_PLACEHOLDER = re.compile(
    r"\{\{\s*("
    r"\$env\.[A-Za-z_][A-Za-z0-9_]*"
    r"|\$[A-Za-z]+"
    r"|[A-Za-z_][A-Za-z0-9_.\-]*"
    r")\s*\}\}"
)

DYNAMIC = {
    "$uuid": lambda: str(uuid.uuid4()),
    "$timestamp": lambda: str(int(datetime.now(UTC).timestamp())),
    "$isoTimestamp": lambda: datetime.now(UTC).isoformat(timespec="seconds"),
    "$randomInt": lambda: str(random.randint(0, 999)),
}


def _resolve(name: str, env: dict[str, Any]) -> str:
    if name.startswith("$env."):
        key = name[5:]
        if key in os.environ:
            return os.environ[key]
        raise KeyError(name)
    if name.startswith("$"):
        if name in DYNAMIC:
            return DYNAMIC[name]()
        raise KeyError(name)
    if name in env:
        return str(env[name])
    raise KeyError(name)


def substitute(text: str, env: dict[str, Any]) -> str:
    """Replace every ``{{ var }}`` in *text*. An unknown variable raises ``KeyError(name)``."""
    return _PLACEHOLDER.sub(lambda m: _resolve(m.group(1), env), text)


def variables_in(text: str) -> list[str]:
    """Return the placeholder names used in *text*, in order of first appearance."""
    return list(dict.fromkeys(m.group(1) for m in _PLACEHOLDER.finditer(text)))


def substitute_all(value: Any, env: dict[str, Any]) -> Any:
    """Apply :func:`substitute` to every string inside nested dicts and lists."""
    if isinstance(value, str):
        return substitute(value, env)
    if isinstance(value, dict):
        return {substitute(str(k), env): substitute_all(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute_all(v, env) for v in value]
    return value
