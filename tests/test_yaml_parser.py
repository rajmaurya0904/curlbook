import json

import pytest

from curlbook.errors import ParseError
from curlbook.yaml_parser import parse_yaml, parse_yaml_document

DOC = """
variables:
  base: https://api.example.com
requests:
  - name: login
    method: post
    url: "{{base}}/login"
    json: {user: raj, n: 1}
    capture:
      token: $.token
    assert:
      - status == 200
      - $.ok == true
  - url: "{{base}}/items"
    query: {page: 2, q: "a b"}
    headers: {X-A: "1"}
    bearer: "{{token}}"
    capture: ["first = $.items[0].id"]
    assert: len($.items) > 0
"""


def test_variables_and_requests():
    doc = parse_yaml_document(DOC)
    assert doc.variables == {"base": "https://api.example.com"}
    assert len(doc.requests) == 2


def test_json_body_sets_content_type_and_method_is_upper_cased():
    login = parse_yaml(DOC)[0]
    assert login["method"] == "POST"
    assert json.loads(login["body"]) == {"user": "raj", "n": 1}
    assert login["headers"]["Content-Type"] == "application/json"


def test_capture_mapping_becomes_specs():
    assert parse_yaml(DOC)[0]["captures"] == ["token = $.token"]
    assert parse_yaml(DOC)[1]["captures"] == ["first = $.items[0].id"]


def test_single_assert_string_and_query_and_bearer():
    items = parse_yaml(DOC)[1]
    assert items["asserts"] == ["len($.items) > 0"]
    assert items["url"] == "{{base}}/items?page=2&q=a%20b"
    assert items["headers"]["Authorization"] == "Bearer {{token}}"
    assert items["method"] == "GET" and items["name"] is None


def test_query_keeps_placeholders_readable():
    r = parse_yaml("- url: http://x\n  query: {id: '{{uid}}'}\n")[0]
    assert r["url"] == "http://x?id={{uid}}"


def test_query_appends_with_ampersand_when_url_has_one():
    r = parse_yaml("- url: http://x?a=1\n  query: {b: 2}\n")[0]
    assert r["url"] == "http://x?a=1&b=2"


def test_bare_list_form_matches_http_parser_shape():
    reqs = parse_yaml("- method: GET\n  url: http://x\n")
    assert set(reqs[0]) == {
        "name",
        "method",
        "url",
        "headers",
        "body",
        "captures",
        "asserts",
        "line",
    }


def test_form_body():
    r = parse_yaml("- url: http://x\n  method: POST\n  form: {a: 1, b: 'x y'}\n")[0]
    assert r["body"] == "a=1&b=x%20y"
    assert r["headers"]["Content-Type"] == "application/x-www-form-urlencoded"


def test_text_body_and_explicit_content_type_is_kept():
    text = "- url: http://x\n  method: POST\n  headers: {content-type: text/plain}\n  body: hi\n"
    r = parse_yaml(text)[0]
    assert r["body"] == "hi" and r["headers"] == {"content-type": "text/plain"}


def test_dict_body_is_serialised_as_json():
    r = parse_yaml("- url: http://x\n  method: PUT\n  body: {a: [1, 2]}\n")[0]
    assert json.loads(r["body"]) == {"a": [1, 2]}


def test_empty_document():
    assert parse_yaml("") == []
    assert parse_yaml("requests: []") == []


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("- method: GET\n", "'url' is required"),
        ("- url: http://x\n  method: FETCH\n", "unknown method"),
        ("- url: http://x\n  asserts: [bogus]\n", "bad assertion"),
        ("- url: http://x\n  capture: {a: nope}\n", "bad capture"),
        ("- url: http://x\n  colour: red\n", "unknown key"),
        ("- url: http://x\n  body: a\n  json: {}\n", "only one of"),
        ("- url: http://x\n  headers: [a]\n", "'headers' must be a mapping"),
        ("- just a string\n", "must be a mapping"),
        ("requests: nope\n", "'requests' must be a list"),
        ("stuff: 1\n", "unknown top-level"),
        ("variables: [1]\nrequests: []\n", "'variables' must be a mapping"),
        ("a: [unclosed\n", "invalid YAML"),
        ("42\n", "must be a list or a mapping"),
        ("- url: http://x\n  assert: [1]\n", "string or a list of strings"),
    ],
)
def test_errors(text, fragment):
    with pytest.raises(ParseError, match=fragment):
        parse_yaml(text)


def test_error_mentions_request_index_and_source():
    with pytest.raises(ParseError) as exc:
        parse_yaml_document("- url: http://x\n- method: GET\n", source="c.yaml")
    assert str(exc.value).startswith("c.yaml: requests[1]")
