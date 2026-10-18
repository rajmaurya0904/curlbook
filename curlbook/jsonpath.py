"""A small JSONPath subset for pulling values out of response bodies.

Supported: ``$`` (root), ``.name``, ``['name']`` / ``["name"]``, ``[3]``, ``[-1]``,
``[*]`` and ``.*``. A path containing a wildcard yields a list of every match;
any other path yields exactly one value.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import ParseError

_NAME = re.compile(r"[A-Za-z0-9_\-]+")
_MISSING = object()


class PathMissing(LookupError):
    """The path is valid but nothing in the document matches it."""


Step = tuple[str, Any]


def parse_path(expr: str) -> list[Step]:
    """Compile a path such as ``$.items[0].id`` into steps. Raises ``ParseError``."""
    text = expr.strip()
    if not text.startswith("$"):
        raise ParseError(f"JSON path must start with '$': {expr!r}")
    steps: list[Step] = []
    i = 1
    while i < len(text):
        ch = text[i]
        if ch == ".":
            if text[i + 1 : i + 2] == "*":
                steps.append(("wild", None))
                i += 2
                continue
            m = _NAME.match(text, i + 1)
            if not m:
                raise ParseError(f"bad JSON path {expr!r}: expected a name after '.' at {i}")
            steps.append(("key", m.group()))
            i = m.end()
        elif ch == "[":
            end = text.find("]", i)
            if end == -1:
                raise ParseError(f"bad JSON path {expr!r}: missing ']'")
            inner = text[i + 1 : end].strip()
            if inner == "*":
                steps.append(("wild", None))
            elif re.fullmatch(r"-?\d+", inner):
                steps.append(("index", int(inner)))
            elif len(inner) >= 2 and inner[0] == inner[-1] and inner[0] in "'\"":
                steps.append(("key", inner[1:-1]))
            else:
                raise ParseError(f"bad JSON path {expr!r}: unsupported subscript [{inner}]")
            i = end + 1
        else:
            raise ParseError(f"bad JSON path {expr!r}: unexpected {ch!r} at position {i}")
    return steps


def has_wildcard(steps: list[Step]) -> bool:
    return any(kind == "wild" for kind, _ in steps)


def _walk(nodes: list[Any], step: Step) -> list[Any]:
    kind, arg = step
    out: list[Any] = []
    for node in nodes:
        if kind == "key":
            if isinstance(node, dict) and arg in node:
                out.append(node[arg])
        elif kind == "index":
            if isinstance(node, list) and -len(node) <= arg < len(node):
                out.append(node[arg])
        elif isinstance(node, list):
            out.extend(node)
        elif isinstance(node, dict):
            out.extend(node.values())
    return out


def lookup(data: Any, expr: str) -> tuple[bool, Any]:
    """Return ``(found, value)``. Wildcard paths are always found and give a list."""
    steps = parse_path(expr)
    nodes = [data]
    for step in steps:
        nodes = _walk(nodes, step)
        if not nodes and not has_wildcard(steps):
            return False, None
    if has_wildcard(steps):
        return True, nodes
    return (True, nodes[0]) if nodes else (False, None)


def extract(data: Any, expr: str) -> Any:
    """Return the value at *expr* or raise :class:`PathMissing`."""
    found, value = lookup(data, expr)
    if not found:
        raise PathMissing(f"{expr} matched nothing")
    return value
