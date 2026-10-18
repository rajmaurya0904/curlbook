"""Parser for ``.http`` files (the format used by VS Code REST Client and JetBrains).

A file is a list of requests separated by ``###`` lines; text after ``###`` names the
request::

    @base = https://api.example.com        # file variable

    ### login
    POST {{base}}/login
    Content-Type: application/json

    {"user": "raj"}

    > capture token = $.token              # directives start with '> '
    > assert status == 200

    ### me
    GET {{base}}/me
    Authorization: Bearer {{token}}

Lines starting with ``#`` or ``//`` before the request line or among the headers are
comments; ``# @name foo`` is another way to name a request.
"""

from __future__ import annotations

import re

from .assertions import parse_assertion
from .captures import parse_capture
from .errors import ParseError
from .model import METHODS, Collection, Request, make_request

_REQUEST_LINE = re.compile(r"^(?P<method>[A-Za-z]+)\s+(?P<url>\S.*?)(?:\s+HTTP/\d(?:\.\d)?)?\s*$")
_BARE_URL = re.compile(r"^(?:https?://|\{\{)\S*$")
_HEADER = re.compile(r"^(?P<name>[A-Za-z0-9!#$%&'*+.^_`|~\-]+)\s*:\s*(?P<value>.*)$")
_VARIABLE = re.compile(r"^@(?P<name>[A-Za-z_][A-Za-z0-9_.\-]*)\s*=\s*(?P<value>.*)$")
_NAME_COMMENT = re.compile(r"^(?:#|//)\s*@name\s+(?P<name>\S.*?)\s*$")
_DIRECTIVE = re.compile(r"^>\s+(?P<kind>\w+)\s*(?P<rest>.*)$")


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith(("#", "//"))


def _split_blocks(lines: list[str]) -> list[tuple[int, str | None, list[tuple[int, str]]]]:
    """Cut the file at ``###`` lines: ``(first_line_no, name_from_separator, lines)``."""
    blocks: list[tuple[int, str | None, list[tuple[int, str]]]] = []
    name: str | None = None
    start = 1
    current: list[tuple[int, str]] = []
    for no, line in enumerate(lines, start=1):
        if line.strip().startswith("###"):
            blocks.append((start, name, current))
            name = line.strip().lstrip("#").strip() or None
            start = no + 1
            current = []
        else:
            current.append((no, line))
    blocks.append((start, name, current))
    return blocks


def _parse_block(
    sep_name: str | None,
    block: list[tuple[int, str]],
    variables: dict[str, str],
    source: str | None,
) -> Request | None:
    def err(msg: str, no: int) -> ParseError:
        return ParseError(msg, line=no, source=source)

    i = 0
    name = sep_name
    # Preamble: blank lines, comments, @variables, then the request line.
    request_no = 0
    request_text = ""
    while i < len(block):
        no, raw = block[i]
        line = raw.strip()
        i += 1
        if not line:
            continue
        nm = _NAME_COMMENT.match(line)
        if nm:
            name = nm.group("name")
            continue
        if _is_comment(line):
            continue
        vm = _VARIABLE.match(line)
        if vm:
            variables[vm.group("name")] = vm.group("value").strip()
            continue
        request_no, request_text = no, line
        break
    if not request_no:
        return None

    m = _REQUEST_LINE.match(request_text)
    if m and m.group("method").upper() in METHODS:
        method, url = m.group("method").upper(), m.group("url")
    elif _BARE_URL.match(request_text):
        method, url = "GET", request_text
    else:
        raise err(
            f"expected a request line such as 'GET https://example.com', got {request_text!r}",
            request_no,
        )
    while i < len(block) and re.match(r"^\s+[?&]", block[i][1]):
        url += block[i][1].strip()
        i += 1

    headers: dict[str, str] = {}
    while i < len(block):
        no, raw = block[i]
        line = raw.strip()
        if not line:
            i += 1
            break
        if _is_comment(line):
            i += 1
            continue
        if line.startswith(">"):
            break
        hm = _HEADER.match(line)
        if not hm:
            raise err(f"expected a header like 'Name: value', got {line!r}", no)
        headers[hm.group("name")] = hm.group("value").strip()
        i += 1

    body_lines: list[str] = []
    captures: list[str] = []
    asserts: list[str] = []
    for no, raw in block[i:]:
        dm = _DIRECTIVE.match(raw.rstrip())
        if not dm:
            body_lines.append(raw.rstrip("\r"))
            continue
        kind, rest = dm.group("kind"), dm.group("rest").strip()
        try:
            if kind == "capture":
                parse_capture(rest)
                captures.append(rest)
            elif kind == "assert":
                parse_assertion(rest)
                asserts.append(rest)
            else:
                raise ParseError(
                    f"unknown directive '> {kind}' (use '> capture' or '> assert')"
                )
        except ParseError as exc:
            raise err(exc.message, no) from exc

    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    return make_request(
        method=method,
        url=url,
        headers=headers,
        body="\n".join(body_lines),
        name=name,
        captures=captures,
        asserts=asserts,
        line=request_no,
    )


def parse_http_document(text: str, source: str | None = None) -> Collection:
    """Parse a ``.http`` file into requests and file-level ``@variables``."""
    variables: dict[str, str] = {}
    requests: list[Request] = []
    for _, sep_name, block in _split_blocks(text.splitlines()):
        req = _parse_block(sep_name, block, variables, source)
        if req is not None:
            requests.append(req)
    return Collection(requests=requests, variables=dict(variables), source=source)


def parse_http(text: str) -> list[Request]:
    """Parse a ``.http`` string into a list of request dictionaries.

    Each dict has ``method``, ``url``, ``headers`` and ``body`` plus ``name``,
    ``captures``, ``asserts`` and ``line``. Raises :class:`ParseError` with a line
    number when a request is malformed.
    """
    return parse_http_document(text).requests
