"""The request and collection shapes shared by every parser and the runner.

A request is a plain dict so it round-trips through JSON and YAML without ceremony:

``name``      optional label (``None`` when unnamed)
``method``    upper-case HTTP method
``url``       URL, possibly containing ``{{ placeholders }}``
``headers``   ``{name: value}``
``body``      request body text (``""`` for none)
``captures``  list of capture specs such as ``"token = $.token"``
``asserts``   list of assertion specs such as ``"status == 200"``
``line``      1-based source line of the request (informational)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT")

Request = dict[str, Any]


def make_request(
    method: str = "GET",
    url: str = "",
    headers: dict[str, str] | None = None,
    body: str = "",
    name: str | None = None,
    captures: list[str] | None = None,
    asserts: list[str] | None = None,
    line: int | None = None,
) -> Request:
    return {
        "name": name,
        "method": method.upper(),
        "url": url,
        "headers": dict(headers or {}),
        "body": body,
        "captures": list(captures or []),
        "asserts": list(asserts or []),
        "line": line,
    }


@dataclass
class Collection:
    """Requests in run order plus the variables the file defines for itself."""

    requests: list[Request] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    source: str | None = None


def display_name(req: Request) -> str:
    """The label shown for a request in reports: its name, else ``METHOD url``."""
    if req.get("name"):
        return str(req["name"])
    return f"{req.get('method', 'GET')} {req.get('url', '')}".strip()
