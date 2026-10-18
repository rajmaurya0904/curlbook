"""The assertion mini-language, e.g. ``status == 200`` or ``$.user.id exists``.

An assertion is ``<subject> <operator> [expected]``.

Subjects
    ``status``            HTTP status code (a number)
    ``time``              elapsed milliseconds (a number)
    ``body``              the raw response text
    ``header NAME``       a response header (case-insensitive name)
    ``$.path``            a value in the JSON body (see :mod:`curlbook.jsonpath`)
    ``len(SUBJECT)``      length of a string, list or object

Operators
    ``==  !=  <  <=  >  >=``   comparison (``expected`` is a JSON literal or bare text)
    ``contains  !contains``   substring, list member or object key
    ``matches``               regular expression search
    ``exists  !exists``       presence
    ``is``                    type: string, number, integer, boolean, array, object, null
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .errors import ParseError
from .jsonpath import lookup, parse_path

OPERATORS = (
    "==", "!=", "<=", ">=", "<", ">", "!contains", "contains", "matches", "!exists", "exists", "is",
)
TYPES = ("string", "number", "integer", "boolean", "array", "object", "null")
_SIMPLE_SUBJECTS = ("status", "time", "body")
_HEADER_RE = re.compile(r"header\s+([A-Za-z0-9!#$%&'*+.^_`|~\-]+)")


@dataclass(frozen=True)
class Assertion:
    text: str
    subject: str  # status | time | body | header | path
    arg: str | None  # header name or JSON path
    op: str
    expected: Any
    length: bool = False


@dataclass(frozen=True)
class Outcome:
    text: str
    ok: bool
    message: str = ""


def _split_path(rest: str) -> tuple[str, str]:
    """Split a leading ``$...`` path from the remainder, honouring quoted brackets."""
    depth = 0
    quote = ""
    for i, ch in enumerate(rest):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"" and depth:
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        elif ch.isspace() and not depth:
            return rest[:i], rest[i:].strip()
    return rest, ""


def _parse_expected(raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def _take_subject(s: str, original: str) -> tuple[str, str | None, str]:
    """Parse a subject at the start of *s*; return ``(subject, arg, remainder)``."""
    s = s.strip()
    if s.startswith("$"):
        path, tail = _split_path(s)
        parse_path(path)
        return "path", path, tail
    hm = _HEADER_RE.match(s)
    if hm:
        return "header", hm.group(1), s[hm.end() :]
    word, _, tail = s.partition(" ")
    if word in _SIMPLE_SUBJECTS:
        return word, None, tail
    raise ParseError(
        f"bad assertion {original!r}: subject must be status, time, body, "
        "header NAME, len(...) or a $.json.path"
    )


def _take_operator(rest: str, original: str) -> tuple[str, str]:
    rest = re.sub(r"^not\s+(exists|contains)\b", r"!\1", rest.strip())
    for op in OPERATORS:
        if not rest.startswith(op):
            continue
        after = rest[len(op) :]
        if op[0].isalpha() or op[0] == "!":
            if after and not after[0].isspace():
                continue
        return op, after.strip()
    raise ParseError(f"bad assertion {original!r}: expected one of {', '.join(OPERATORS)}")


def parse_assertion(text: str) -> Assertion:
    """Parse one assertion line. Raises :class:`ParseError` on bad syntax."""
    src = text.strip()
    if src.startswith("assert "):
        src = src[7:].strip()
    length = False
    lm = re.match(r"len\(\s*(.*?)\s*\)\s*(.*)$", src, re.S)
    if lm:
        length = True
        subject, arg, leftover = _take_subject(lm.group(1), text)
        if leftover.strip():
            raise ParseError(f"bad assertion {text!r}: unexpected {leftover.strip()!r} in len()")
        rest = lm.group(2)
    else:
        subject, arg, rest = _take_subject(src, text)

    op, expected_raw = _take_operator(rest, text)
    if op in ("exists", "!exists"):
        if expected_raw:
            raise ParseError(f"bad assertion {text!r}: '{op}' takes no value")
        expected: Any = None
    else:
        if expected_raw == "":
            raise ParseError(f"bad assertion {text!r}: '{op}' needs a value")
        expected = _parse_expected(expected_raw)
        if op == "is" and expected not in TYPES:
            raise ParseError(f"bad assertion {text!r}: type must be one of {', '.join(TYPES)}")
        if op == "matches":
            try:
                re.compile(str(expected))
            except re.error as exc:
                raise ParseError(f"bad assertion {text!r}: invalid regex ({exc})") from exc
        if op in ("<", "<=", ">", ">=") and not _is_number(_coerce_number(expected)):
            raise ParseError(f"bad assertion {text!r}: '{op}' needs a number")
    return Assertion(src, subject, arg, op, expected, length)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coerce_number(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _describe(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else repr(value)
    return text if len(text) <= 80 else text[:77] + "..."


def _type_of(value: Any) -> set[str]:
    if value is None:
        return {"null"}
    if isinstance(value, bool):
        return {"boolean"}
    if isinstance(value, int):
        return {"number", "integer"}
    if isinstance(value, float):
        return {"number", "integer"} if value.is_integer() else {"number"}
    if isinstance(value, str):
        return {"string"}
    if isinstance(value, list):
        return {"array"}
    return {"object"}


def _equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) != isinstance(expected, bool):
        return False
    if _is_number(actual) and isinstance(expected, str):
        expected = _coerce_number(expected)
    if isinstance(actual, str) and _is_number(expected):
        return actual == str(expected)
    return actual == expected


def _resolve_subject(a: Assertion, resp: Any) -> tuple[bool, Any, str]:
    """Return ``(found, value, label)`` for the assertion's subject."""
    if a.subject == "status":
        return True, resp.status_code, "status"
    if a.subject == "time":
        return True, resp.elapsed_ms, "time"
    if a.subject == "body":
        return True, resp.text, "body"
    if a.subject == "header":
        value = resp.headers.get(a.arg)
        return value is not None, value, f"header {a.arg}"
    try:
        data = resp.json()
    except ValueError:
        return False, "response body is not JSON", str(a.arg)
    found, value = lookup(data, a.arg)
    return found, value, str(a.arg)


def evaluate(assertion: Assertion | str, resp: Any) -> Outcome:
    """Check one assertion against a response and report the outcome."""
    a = parse_assertion(assertion) if isinstance(assertion, str) else assertion
    found, value, label = _resolve_subject(a, resp)
    if a.length:
        label = f"len({label})"
    if not found and isinstance(value, str) and value.startswith("response body"):
        return Outcome(a.text, False, value)

    if a.op == "exists":
        return Outcome(a.text, found, "" if found else f"{label} is missing")
    if a.op == "!exists":
        return Outcome(a.text, not found, "" if not found else f"{label} exists")
    if not found:
        return Outcome(a.text, False, f"{label} is missing")

    if a.length:
        if not isinstance(value, (str, list, dict)):
            return Outcome(a.text, False, f"{label}: value has no length ({_describe(value)})")
        value = len(value)

    ok = _compare(a, value)
    if ok is None:
        return Outcome(a.text, False, f"{label}: cannot apply '{a.op}' to {_describe(value)}")
    if ok:
        return Outcome(a.text, True)
    return Outcome(a.text, False, f"{label}: expected {a.op} {_describe(a.expected)}, "
                   f"got {_describe(value)}")


def _compare(a: Assertion, value: Any) -> bool | None:
    op, expected = a.op, a.expected
    if op == "==":
        return _equal(value, expected)
    if op == "!=":
        return not _equal(value, expected)
    if op in ("<", "<=", ">", ">="):
        left, right = _coerce_number(value), _coerce_number(expected)
        if not (_is_number(left) and _is_number(right)):
            return None
        return {"<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right}[op]
    if op in ("contains", "!contains"):
        if isinstance(value, str):
            hit = str(expected) in value
        elif isinstance(value, list):
            hit = any(_equal(item, expected) for item in value)
        elif isinstance(value, dict):
            hit = str(expected) in value
        else:
            return None
        return hit if op == "contains" else not hit
    if op == "matches":
        text = value if isinstance(value, str) else json.dumps(value)
        return re.search(str(expected), text) is not None
    if op == "is":
        return expected in _type_of(value)
    return None


def assert_response(resp: Any, spec: str | list[str]) -> list[Outcome]:
    """Evaluate one or more assertions; raise ``AssertionError`` listing every failure."""
    specs = [spec] if isinstance(spec, str) else list(spec)
    outcomes = [evaluate(s, resp) for s in specs]
    failed = [o for o in outcomes if not o.ok]
    if failed:
        raise AssertionError("; ".join(f"{o.text} -> {o.message}" for o in failed))
    return outcomes
