"""run_collection with real requests to the local test server."""

from __future__ import annotations

from curlbook.engine import resolve_variables, run_collection
from curlbook.http_parser import parse_http
from curlbook.model import make_request
from curlbook.runner import RequestFailed, Response

LOGIN_FLOW = """\
### login
POST {{base}}/login
Content-Type: application/json

{"user": "{{user}}"}

> capture token = $.token
> capture uid = $.user.id
> assert status == 200
> assert header X-Request-Id exists

### me
GET {{base}}/me
Authorization: Bearer {{token}}

> assert status == 200
> assert $.id == {{uid}}
> assert $.roles contains admin
"""


def test_chaining_passes_a_token_between_requests(server) -> None:
    env = {"base": server, "user": "raj"}
    results = run_collection(parse_http(LOGIN_FLOW), env)
    assert [r.passed for r in results] == [True, True]
    assert env["token"] == "abc123"
    assert env["uid"] == 7
    assert results[0].captured == {"token": "abc123", "uid": 7}
    assert results[1].status == 200


def test_chain_breaks_visibly_when_the_first_step_fails(server) -> None:
    env = {"base": server, "user": "nobody"}
    first, second = run_collection(parse_http(LOGIN_FLOW), env)
    assert not first.passed
    assert any("status == 200" in line for line in first.failures)
    assert any("capture token" in line for line in first.failures)
    assert not second.passed
    assert "undefined variable {{ token }}" in second.error


def test_failed_assertion_message_has_expected_and_actual(server) -> None:
    reqs = [make_request("GET", f"{server}/status/418", asserts=["status == 200"])]
    (res,) = run_collection(reqs, {})
    assert res.status == 418
    assert res.failures == ["status == 200: status: expected == 200, got 418"]


def test_request_without_asserts_fails_on_error_status(server) -> None:
    ok, bad = run_collection(
        [make_request("GET", f"{server}/items"), make_request("GET", f"{server}/status/500")], {}
    )
    assert ok.passed and not bad.passed
    assert "must be < 400" in bad.failures[0]


def test_expected_error_status_can_pass(server) -> None:
    (res,) = run_collection(
        [make_request("GET", f"{server}/status/404", asserts=["status == 404"])], {}
    )
    assert res.passed


def test_undefined_variable_is_reported_and_nothing_is_sent(server) -> None:
    from tests.conftest import Handler

    (res,) = run_collection([make_request("GET", f"{server}/{{{{ nope }}}}")], {})
    assert res.error == "undefined variable {{ nope }}"
    assert Handler.log == []


def test_connection_error_is_a_failed_result_not_an_exception() -> None:
    def boom(req):
        raise RequestFailed("connection failed: refused")

    (res,) = run_collection([make_request("GET", "http://x.test/")], {}, execute=boom)
    assert res.error == "connection failed: refused"
    assert not res.passed and res.status is None


def test_bad_assertion_syntax_is_reported_per_request(server) -> None:
    (res,) = run_collection(
        [make_request("GET", f"{server}/items", asserts=["status is-ish 200"])], {}
    )
    assert "bad assertion" in res.error


def test_fail_fast_skips_the_rest(server) -> None:
    reqs = [
        make_request("GET", f"{server}/status/500", asserts=["status == 200"]),
        make_request("GET", f"{server}/items"),
    ]
    first, second = run_collection(reqs, {}, fail_fast=True)
    assert not first.passed
    assert second.skipped and not second.passed and second.status is None


def test_without_fail_fast_every_request_runs(server) -> None:
    reqs = [
        make_request("GET", f"{server}/status/500", asserts=["status == 200"]),
        make_request("GET", f"{server}/items"),
    ]
    results = run_collection(reqs, {})
    assert [r.passed for r in results] == [False, True]


def test_variables_are_substituted_in_headers_and_body(server) -> None:
    req = make_request(
        "POST",
        f"{server}/echo?x={{{{n}}}}",
        {"X-Who": "{{who}}"},
        body='{"n": {{n}}}',
        asserts=["$.headers.x-who == raj-m", "$.query.x[0] == 5", "$.body contains 5"],
    )
    (res,) = run_collection([req], {"who": "raj-m", "n": 5})
    assert res.passed, res.failures


def test_assertions_may_reference_variables(server) -> None:
    req = make_request("GET", f"{server}/me", {"Authorization": "Bearer {{t}}"},
                       asserts=["$.name == {{name}}"])
    (res,) = run_collection([req], {"t": "abc123", "name": "raj"})
    assert res.passed, res.failures


def test_custom_executor_and_callback() -> None:
    seen = []

    def fake(req):
        return Response(201, {"Content-Type": "application/json"}, '{"ok": true}', 1.0)

    results = run_collection(
        [make_request("POST", "http://x.test/a", asserts=["status == 201", "$.ok == true"])],
        {},
        execute=fake,
        on_result=seen.append,
    )
    assert results == seen and results[0].passed


def test_resolve_variables_expands_references_in_order() -> None:
    out = resolve_variables({"a": "x", "b": "{{a}}-y", "c": "{{later}}", "n": 3}, {"env": "e"})
    assert out == {"a": "x", "b": "x-y", "c": "{{later}}", "n": 3}


def test_resolve_variables_can_use_the_environment() -> None:
    assert resolve_variables({"url": "{{host}}/api"}, {"host": "http://h"}) == {
        "url": "http://h/api"
    }
