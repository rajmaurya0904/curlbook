"""Send one request and wrap the reply in a small Response object."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import requests

from .errors import CurlbookError
from .model import Request


class RequestFailed(CurlbookError):
    """The request never produced a response: bad URL, refused connection, timeout."""


@dataclass
class Response:
    """What assertions and captures look at. Header lookup is case-insensitive."""

    status_code: int
    headers: Mapping[str, str]
    text: str
    elapsed_ms: float
    url: str = ""
    reason: str = ""

    def json(self) -> Any:
        """Decode the body as JSON. Raises ``ValueError`` when it is not JSON."""
        return json.loads(self.text)


_CHARSET = re.compile(r"charset=", re.I)


def _decode(resp: requests.Response) -> str:
    """Bodies without an explicit charset are read as UTF-8, not guessed."""
    if _CHARSET.search(resp.headers.get("Content-Type", "")) and resp.encoding:
        return resp.content.decode(resp.encoding, errors="replace")
    return resp.content.decode("utf-8", errors="replace")


def execute_request(
    req: Request,
    *,
    timeout: float = 30.0,
    verify: bool = True,
    allow_redirects: bool = True,
    session: requests.Session | None = None,
) -> Response:
    """Send *req* (already substituted) and return the response.

    Raises :class:`RequestFailed` when no response arrives. HTTP error statuses are
    ordinary responses, not exceptions.
    """
    url = str(req.get("url", "")).strip()
    if not re.match(r"^https?://", url, re.I):
        raise RequestFailed(f"URL must start with http:// or https://, got {url!r}")
    body = req.get("body") or ""
    client = session or requests
    started = time.perf_counter()
    try:
        raw = client.request(
            str(req.get("method", "GET")).upper(),
            url,
            headers=req.get("headers") or {},
            data=body.encode("utf-8") if body else None,
            timeout=timeout,
            verify=verify,
            allow_redirects=allow_redirects,
        )
    except requests.Timeout:
        raise RequestFailed(f"timed out after {timeout:g}s") from None
    except requests.exceptions.SSLError as exc:
        detail = _root_cause(exc)
        raise RequestFailed(f"TLS error: {detail} (use --insecure to skip checks)") from None
    except requests.ConnectionError as exc:
        raise RequestFailed(f"connection failed: {_root_cause(exc)}") from None
    except (requests.RequestException, ValueError) as exc:
        raise RequestFailed(str(exc)) from None
    elapsed = (time.perf_counter() - started) * 1000
    return Response(
        status_code=raw.status_code,
        headers=raw.headers,
        text=_decode(raw),
        elapsed_ms=round(elapsed, 1),
        url=raw.url,
        reason=raw.reason or "",
    )


def _root_cause(exc: BaseException) -> str:
    """The innermost message of a nested urllib3/requests exception, shortened."""
    seen = exc
    while True:
        nxt = seen.__cause__ or seen.__context__
        if nxt is None or nxt is seen:
            break
        seen = nxt
    arg = seen.args[0] if seen.args else seen
    text = getattr(arg, "reason", None) or arg
    text = re.sub(r"\s+", " ", str(text))
    return text if len(text) <= 160 else text[:157] + "..."
