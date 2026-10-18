import json

import pytest

from curlbook.captures import CaptureError, apply_capture, parse_capture
from curlbook.errors import ParseError


class Resp:
    status_code = 200
    elapsed_ms = 5.0
    text = json.dumps({"token": "abc", "user": {"id": 9}, "items": [{"id": 1}, {"id": 2}]})
    headers = {"x-session": "s1"}

    def json(self):
        return json.loads(self.text)


def test_capture_json_path():
    assert apply_capture(parse_capture("token = $.token"), Resp()) == "abc"


def test_capture_nested_and_wildcard():
    assert apply_capture(parse_capture("uid = $.user.id"), Resp()) == 9
    assert apply_capture(parse_capture("ids = $.items[*].id"), Resp()) == [1, 2]


def test_capture_header_status_body():
    assert apply_capture(parse_capture("sid = header x-session"), Resp()) == "s1"
    assert apply_capture(parse_capture("code = status"), Resp()) == 200
    assert apply_capture(parse_capture("raw = body"), Resp()).startswith("{")


def test_leading_keyword_is_optional():
    assert parse_capture("capture token = $.token").name == "token"


def test_missing_path_raises_capture_error_naming_the_variable():
    with pytest.raises(CaptureError, match="nope: .*nothing"):
        apply_capture(parse_capture("nope = $.nope"), Resp())


def test_missing_header_raises():
    with pytest.raises(CaptureError, match="no header x-other"):
        apply_capture(parse_capture("o = header x-other"), Resp())


def test_non_json_body_raises():
    class Html(Resp):
        text = "<html>"

        def json(self):
            raise ValueError("nope")

    with pytest.raises(CaptureError, match="not JSON"):
        apply_capture(parse_capture("t = $.a"), Html())


@pytest.mark.parametrize("bad", ["", "token", "= $.a", "1x = $.a", "a = banana", "a = $.b extra"])
def test_bad_capture_syntax(bad):
    with pytest.raises(ParseError):
        parse_capture(bad)
