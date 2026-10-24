"""Run a collection: substitute variables, send, capture, assert, repeat."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .assertions import Outcome, evaluate, parse_assertion
from .captures import CaptureError, apply_capture, parse_capture
from .errors import CurlbookError, ParseError
from .model import Request, display_name
from .runner import RequestFailed, Response, execute_request
from .subst import substitute, substitute_all

Executor = Callable[[Request], Response]


@dataclass
class RequestResult:
    """Everything that happened to one request."""

    index: int
    name: str
    method: str
    url: str
    status: int | None = None
    elapsed_ms: float | None = None
    outcomes: list[Outcome] = field(default_factory=list)
    error: str | None = None
    captured: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False

    @property
    def passed(self) -> bool:
        return not self.skipped and self.error is None and all(o.ok for o in self.outcomes)

    @property
    def failures(self) -> list[str]:
        """One line per thing that went wrong."""
        lines = [f"{o.text}: {o.message}" for o in self.outcomes if not o.ok]
        return ([self.error] if self.error else []) + lines


def _undefined(exc: KeyError) -> str:
    return f"undefined variable {{{{ {exc.args[0]} }}}}"


def run_request(
    req: Request,
    env: dict[str, Any],
    index: int,
    execute: Executor,
) -> RequestResult:
    """Run one request. *env* gains any variables the request captures."""
    result = RequestResult(index, display_name(req), req.get("method", "GET"), req.get("url", ""))
    try:
        sent = {
            **req,
            "url": substitute(req["url"], env),
            "headers": substitute_all(req.get("headers") or {}, env),
            "body": substitute(req.get("body") or "", env),
        }
        result.url = sent["url"]
        captures = [parse_capture(substitute(c, env)) for c in req.get("captures", [])]
        asserts = [parse_assertion(substitute(a, env)) for a in req.get("asserts", [])]
    except KeyError as exc:
        result.error = _undefined(exc)
        return result
    except ParseError as exc:
        result.error = exc.message
        return result

    try:
        resp = execute(sent)
    except RequestFailed as exc:
        result.error = str(exc)
        return result
    except CurlbookError as exc:
        result.error = str(exc)
        return result

    result.status = resp.status_code
    result.elapsed_ms = resp.elapsed_ms

    for cap in captures:
        try:
            value = apply_capture(cap, resp)
        except CaptureError as exc:
            result.outcomes.append(Outcome(f"capture {cap.text}", False, str(exc)))
            continue
        env[cap.name] = value
        result.captured[cap.name] = value

    for a in asserts:
        result.outcomes.append(evaluate(a, resp))
    if not asserts:
        ok = resp.status_code < 400
        msg = "" if ok else f"status {resp.status_code} (a request without asserts must be < 400)"
        result.outcomes.append(Outcome("status < 400 (implicit)", ok, msg))
    return result


def run_collection(
    requests: list[Request],
    env: dict[str, Any] | None = None,
    *,
    execute: Executor | None = None,
    fail_fast: bool = False,
    timeout: float = 30.0,
    verify: bool = True,
    on_result: Callable[[RequestResult], None] | None = None,
) -> list[RequestResult]:
    """Run *requests* in order and return one result each.

    *env* is updated in place with captured values, so later requests (and the caller)
    see them. With ``fail_fast`` the first failing request stops the run and the rest
    are reported as skipped. ``on_result`` is called as each request finishes.
    """
    env = env if env is not None else {}
    if execute is None:

        def execute(req: Request) -> Response:
            return execute_request(req, timeout=timeout, verify=verify)

    results: list[RequestResult] = []
    stopped = False
    for i, req in enumerate(requests, start=1):
        if stopped:
            res = RequestResult(i, display_name(req), req.get("method", "GET"), req.get("url", ""))
            res.skipped = True
        else:
            res = run_request(req, env, i, execute)
            stopped = fail_fast and not res.passed
        results.append(res)
        if on_result:
            on_result(res)
    return results


def resolve_variables(variables: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    """Expand ``{{ }}`` references inside a collection's own variables.

    Later variables may use earlier ones and anything already in *base*. A reference
    that cannot be resolved is left as written so a later environment can supply it.
    """
    out: dict[str, Any] = {}
    scope = dict(base)
    for key, value in variables.items():
        if isinstance(value, str):
            try:
                value = substitute(value, scope)
            except KeyError:
                pass
        out[key] = value
        scope[key] = value
    return out
