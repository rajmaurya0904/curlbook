"""Parser for YAML request collections.

Either a bare list of requests or a mapping with ``variables`` and ``requests``::

    variables:
      base: https://api.example.com
    requests:
      - name: login
        method: POST
        url: "{{base}}/login"
        json: {user: raj}
        capture:
          token: $.token
        assert:
          - status == 200

Request keys: ``name``, ``method`` (default GET), ``url``, ``headers``, ``query``
(mapping appended to the URL), one of ``body`` / ``json`` / ``form``, ``bearer``
(token for an ``Authorization: Bearer`` header), ``capture`` (mapping
``variable: subject`` or list of ``"variable = subject"``) and ``assert`` (list of
assertion strings).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlencode

import yaml

from .assertions import parse_assertion
from .captures import parse_capture
from .errors import ParseError
from .model import METHODS, Collection, Request, make_request

_KEYS = {
    "name",
    "method",
    "url",
    "headers",
    "query",
    "body",
    "json",
    "form",
    "bearer",
    "capture",
    "captures",
    "assert",
    "asserts",
}


def _as_list(value: Any, where: str, source: str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return list(value)
    raise ParseError(f"{where} must be a string or a list of strings", source=source)


def _encode(mapping: dict) -> str:
    # Keep {{placeholders}} readable; they are substituted before the request is sent.
    return urlencode({str(k): str(v) for k, v in mapping.items()}, safe="{}", quote_via=quote)


def _parse_request(item: Any, index: int, source: str | None) -> Request:
    where = f"requests[{index}]"
    if not isinstance(item, dict):
        raise ParseError(f"{where} must be a mapping, got {type(item).__name__}", source=source)
    unknown = sorted(set(item) - _KEYS)
    if unknown:
        raise ParseError(f"{where}: unknown key(s) {', '.join(map(str, unknown))}", source=source)
    url = item.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ParseError(f"{where}: 'url' is required", source=source)
    method = str(item.get("method", "GET")).upper()
    if method not in METHODS:
        raise ParseError(f"{where}: unknown method {method!r}", source=source)

    headers = item.get("headers") or {}
    if not isinstance(headers, dict):
        raise ParseError(f"{where}: 'headers' must be a mapping", source=source)
    headers = {str(k): str(v) for k, v in headers.items()}

    query = item.get("query")
    if query:
        if not isinstance(query, dict):
            raise ParseError(f"{where}: 'query' must be a mapping", source=source)
        url += ("&" if "?" in url else "?") + _encode(query)

    given = [k for k in ("body", "json", "form") if k in item]
    if len(given) > 1:
        raise ParseError(f"{where}: use only one of body, json or form", source=source)
    body = ""
    lowered = {k.lower() for k in headers}
    if "json" in item:
        body = json.dumps(item["json"], ensure_ascii=False)
        if "content-type" not in lowered:
            headers["Content-Type"] = "application/json"
    elif "form" in item:
        if not isinstance(item["form"], dict):
            raise ParseError(f"{where}: 'form' must be a mapping", source=source)
        body = _encode(item["form"])
        if "content-type" not in lowered:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif "body" in item:
        raw = item["body"]
        if isinstance(raw, (dict, list)):
            body = json.dumps(raw, ensure_ascii=False)
            if "content-type" not in lowered:
                headers["Content-Type"] = "application/json"
        elif raw is not None:
            body = str(raw).rstrip("\n")

    if "bearer" in item:
        headers.setdefault("Authorization", f"Bearer {item['bearer']}")

    raw_captures = item.get("capture", item.get("captures"))
    if isinstance(raw_captures, dict):
        captures = [f"{k} = {v}" for k, v in raw_captures.items()]
    else:
        captures = _as_list(raw_captures, f"{where}: 'capture'", source)
    asserts = _as_list(item.get("assert", item.get("asserts")), f"{where}: 'assert'", source)
    try:
        for spec in captures:
            parse_capture(spec)
        for spec in asserts:
            parse_assertion(spec)
    except ParseError as exc:
        raise ParseError(f"{where}: {exc.message}", source=source) from exc

    name = item.get("name")
    return make_request(
        method=method,
        url=url.strip(),
        headers=headers,
        body=body,
        name=str(name) if name is not None else None,
        captures=captures,
        asserts=asserts,
    )


def parse_yaml_document(text: str, source: str | None = None) -> Collection:
    """Parse a YAML collection into requests and file-level variables."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ParseError(f"invalid YAML: {exc}", source=source) from exc
    variables: dict[str, Any] = {}
    if data is None:
        items: list[Any] = []
    elif isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        unknown = sorted(set(data) - {"variables", "requests"})
        if unknown:
            raise ParseError(
                f"unknown top-level key(s) {', '.join(map(str, unknown))} "
                "(expected 'variables' and 'requests')",
                source=source,
            )
        variables = data.get("variables") or {}
        if not isinstance(variables, dict):
            raise ParseError("'variables' must be a mapping", source=source)
        items = data.get("requests") or []
        if not isinstance(items, list):
            raise ParseError("'requests' must be a list", source=source)
    else:
        raise ParseError("a collection must be a list or a mapping", source=source)
    requests = [_parse_request(item, i, source) for i, item in enumerate(items)]
    return Collection(requests=requests, variables=dict(variables), source=source)


def parse_yaml(text: str) -> list[Request]:
    """Parse a YAML collection into a list of request dicts (same shape as ``parse_http``)."""
    return parse_yaml_document(text).requests
