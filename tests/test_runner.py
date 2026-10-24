"""execute_request against a real local HTTP server."""

from __future__ import annotations

import socket

import pytest

from curlbook.model import make_request
from curlbook.runner import RequestFailed, execute_request


def test_get_returns_status_headers_and_json(server) -> None:
    resp = execute_request(make_request("GET", f"{server}/me", {"Authorization": "Bearer abc123"}))
    assert resp.status_code == 200
    assert resp.json()["name"] == "raj"
    assert resp.headers["content-type"] == "application/json"  # case-insensitive
    assert resp.elapsed_ms > 0


def test_post_sends_body_and_headers(server) -> None:
    req = make_request("POST", f"{server}/echo", {"X-Test": "yes"}, body='{"a": "café"}')
    echoed = execute_request(req).json()
    assert echoed["method"] == "POST"
    assert echoed["headers"]["x-test"] == "yes"
    assert echoed["body"] == '{"a": "café"}'


def test_error_status_is_a_response_not_an_exception(server) -> None:
    resp = execute_request(make_request("GET", f"{server}/status/503"))
    assert resp.status_code == 503


def test_utf8_body_without_charset_is_decoded_as_utf8(server) -> None:
    assert execute_request(make_request("GET", f"{server}/text")).text == "héllo"


def test_non_json_body_raises_value_error(server) -> None:
    with pytest.raises(ValueError):
        execute_request(make_request("GET", f"{server}/text")).json()


def test_timeout_is_reported(server) -> None:
    with pytest.raises(RequestFailed, match="timed out after 0.2s"):
        execute_request(make_request("GET", f"{server}/slow"), timeout=0.2)


def test_connection_refused_is_reported() -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(RequestFailed, match="connection failed"):
        execute_request(make_request("GET", f"http://127.0.0.1:{port}/"), timeout=10)


@pytest.mark.parametrize("url", ["", "ftp://example.com/x", "example.com/x", "{{base}}/x"])
def test_non_http_urls_are_rejected(url: str) -> None:
    with pytest.raises(RequestFailed, match="must start with http"):
        execute_request(make_request("GET", url))


def test_redirects_can_be_disabled(server) -> None:
    resp = execute_request(make_request("GET", f"{server}/status/302"), allow_redirects=False)
    assert resp.status_code == 302
