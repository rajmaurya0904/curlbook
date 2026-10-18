import json

import pytest

from curlbook.assertions import assert_response, evaluate, parse_assertion
from curlbook.errors import ParseError


class Resp:
    def __init__(self, status=200, body=None, headers=None, text=None, elapsed_ms=12.0):
        self.status_code = status
        self.text = text if text is not None else json.dumps(body)
        self._body = body
        self.elapsed_ms = elapsed_ms
        self.headers = _CI(headers or {})

    def json(self):
        if self._body is None and not self.text.strip().startswith(("{", "[")):
            raise ValueError("no json")
        return json.loads(self.text)


class _CI(dict):
    def __init__(self, d):
        super().__init__({k.lower(): v for k, v in d.items()})

    def get(self, key, default=None):
        return super().get(key.lower(), default)


BODY = {"ok": True, "id": 7, "name": "raj", "tags": ["a", "b"], "n": None, "score": 4.5,
        "user": {"email": "r@example.com"}}
R = Resp(201, BODY, {"Content-Type": "application/json; charset=utf-8", "X-Id": "42"})


@pytest.mark.parametrize(
    "text",
    [
        "status == 201",
        "status != 200",
        "status >= 200",
        "status < 300",
        "time < 1000",
        "header content-type contains json",
        "header Content-Type matches ^application/",
        "header x-id == 42",
        "header x-id exists",
        "header x-missing !exists",
        "header x-missing not exists",
        "$.ok == true",
        "$.id == 7",
        "$.name == raj",
        '$.name == "raj"',
        "$.tags contains a",
        "$.tags !contains z",
        "len($.tags) == 2",
        "len($.name) == 3",
        "$.n == null",
        "$.n exists",
        "$.missing !exists",
        "$.score > 4",
        "$.id is integer",
        "$.score is number",
        "$.name is string",
        "$.tags is array",
        "$.user is object",
        "$.ok is boolean",
        "$.user.email matches ^[^@]+@example[.]com$",
        "$.tags[*] contains b",
        "$.tags == [\"a\", \"b\"]",
        "body contains raj",
        "assert status == 201",
    ],
)
def test_passing_assertions(text):
    out = evaluate(text, R)
    assert out.ok, out.message


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("status == 200", "expected == 200, got 201"),
        ("status > 500", "status: expected > 500"),
        ("$.id == 8", "$.id: expected == 8, got 7"),
        ("$.ok == 1", "got true"),
        ("$.missing == 1", "$.missing is missing"),
        ("header x-nope == 1", "header x-nope is missing"),
        ("$.tags contains z", "expected contains"),
        ("len($.tags) == 3", "len($.tags): expected == 3, got 2"),
        ("len($.id) == 1", "no length"),
        ("$.name > 3", "cannot apply '>'"),
        ("$.id is string", "expected is 'string'"),
        ("$.user.email matches ^zzz", "expected matches"),
        ("$.ok exists_not", "bad assertion"),
    ],
)
def test_failing_assertions(text, fragment):
    if "bad assertion" in fragment:
        with pytest.raises(ParseError, match=fragment):
            evaluate(text, R)
        return
    out = evaluate(text, R)
    assert not out.ok
    assert fragment in out.message


def test_json_assertion_on_non_json_body_fails_cleanly():
    out = evaluate("$.a == 1", Resp(200, None, text="<html>"))
    assert not out.ok
    assert "not JSON" in out.message


def test_bool_is_not_equal_to_one():
    assert not evaluate("$.ok == 1", R).ok
    assert evaluate("$.ok == true", R).ok


def test_string_number_coercion():
    assert evaluate("status == 201", R).ok
    assert evaluate('$.id == "7"', R).ok  # a numeric value equals its string form


def test_quoted_bracket_path_with_space():
    resp = Resp(200, {"a b": {"c": 1}})
    assert evaluate("$['a b'].c == 1", resp).ok


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "banana == 1",
        "status",
        "status ==",
        "status exists extra",
        "$.a is purple",
        "$.a matches (",
        "status < abc",
        "$bad == 1",
        "len($.a b) == 1",
    ],
)
def test_parse_errors(bad):
    with pytest.raises(ParseError):
        parse_assertion(bad)


def test_assert_response_raises_with_every_failure():
    with pytest.raises(AssertionError) as exc:
        assert_response(R, ["status == 200", "$.id == 7", "$.name == bob"])
    msg = str(exc.value)
    assert "status == 200" in msg and "$.name == bob" in msg and "$.id == 7 ->" not in msg


def test_assert_response_returns_outcomes_when_all_pass():
    outcomes = assert_response(R, "status == 201")
    assert [o.ok for o in outcomes] == [True]


def test_parsed_assertion_fields():
    a = parse_assertion("assert len($.items) >= 2")
    assert (a.subject, a.arg, a.op, a.expected, a.length) == ("path", "$.items", ">=", 2, True)
    h = parse_assertion("header X-Request-Id exists")
    assert (h.subject, h.arg, h.op) == ("header", "X-Request-Id", "exists")
