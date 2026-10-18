"""Capture directives: pull a value out of a response into a variable.

Syntax: ``NAME = SUBJECT`` where SUBJECT is anything the assertion language accepts
as a subject: ``$.json.path``, ``header NAME``, ``status``, ``time`` or ``body``.
The captured value is available to every later request as ``{{ NAME }}``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .assertions import take_subject
from .errors import CurlbookError, ParseError
from .jsonpath import lookup

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-]*$")


class CaptureError(CurlbookError):
    """The response did not contain the value a capture asked for."""


@dataclass(frozen=True)
class Capture:
    name: str
    subject: str
    arg: str | None
    text: str


def parse_capture(text: str) -> Capture:
    """Parse ``NAME = SUBJECT``. Raises :class:`ParseError`."""
    src = text.strip()
    if src.startswith("capture "):
        src = src[8:].strip()
    name, eq, rhs = src.partition("=")
    name = name.strip()
    if not eq or not _NAME.match(name):
        raise ParseError(f"bad capture {text!r}: expected NAME = SUBJECT, e.g. token = $.token")
    subject, arg, leftover = take_subject(rhs, text)
    if leftover.strip():
        raise ParseError(f"bad capture {text!r}: unexpected {leftover.strip()!r}")
    return Capture(name, subject, arg, src)


def apply_capture(capture: Capture, resp: Any) -> Any:
    """Return the captured value or raise :class:`CaptureError`."""
    if capture.subject == "status":
        return resp.status_code
    if capture.subject == "time":
        return resp.elapsed_ms
    if capture.subject == "body":
        return resp.text
    if capture.subject == "header":
        value = resp.headers.get(capture.arg)
        if value is None:
            raise CaptureError(f"{capture.name}: response has no header {capture.arg}")
        return value
    try:
        data = resp.json()
    except ValueError as exc:
        raise CaptureError(f"{capture.name}: response body is not JSON") from exc
    found, value = lookup(data, capture.arg or "$")
    if not found:
        raise CaptureError(f"{capture.name}: {capture.arg} matched nothing in the response")
    return value
