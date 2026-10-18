import pytest

from curlbook.errors import ParseError
from curlbook.http_parser import parse_http, parse_http_document

DOC = """\
@base = https://api.example.com
@user = raj

### login
# a comment
POST {{base}}/login HTTP/1.1
Content-Type: application/json
// another comment
Accept: */*

{"user": "{{user}}"}

> capture token = $.token
> assert status == 200
> assert $.ok == true

### me
GET {{base}}/me
  ?verbose=1
  &fmt=json
Authorization: Bearer {{token}}

###

# @name health
https://api.example.com/health
"""


def test_names_come_from_separator_or_name_comment():
    reqs = parse_http(DOC)
    assert [r["name"] for r in reqs] == ["login", "me", "health"]


def test_file_variables_are_collected():
    doc = parse_http_document(DOC)
    assert doc.variables == {"base": "https://api.example.com", "user": "raj"}


def test_headers_skip_comments_and_keep_case():
    login = parse_http(DOC)[0]
    assert login["headers"] == {"Content-Type": "application/json", "Accept": "*/*"}


def test_http_version_is_dropped_from_the_url():
    assert parse_http(DOC)[0]["url"] == "{{base}}/login"


def test_query_continuation_lines_extend_the_url():
    assert parse_http(DOC)[1]["url"] == "{{base}}/me?verbose=1&fmt=json"


def test_directives_are_removed_from_the_body_and_collected():
    login = parse_http(DOC)[0]
    assert login["body"] == '{"user": "{{user}}"}'
    assert login["captures"] == ["token = $.token"]
    assert login["asserts"] == ["status == 200", "$.ok == true"]


def test_bare_url_means_get():
    health = parse_http(DOC)[2]
    assert (health["method"], health["url"]) == ("GET", "https://api.example.com/health")


def test_methods_are_upper_cased():
    assert parse_http("post http://x/y\n")[0]["method"] == "POST"


def test_request_without_blank_line_before_directive():
    r = parse_http("GET http://x\nAccept: a\n> assert status == 200\n")[0]
    assert r["asserts"] == ["status == 200"] and r["body"] == ""


def test_multiline_body_keeps_inner_blank_lines_but_trims_edges():
    text = "POST http://x\nContent-Type: text/plain\n\n\nline1\n\nline3\n\n\n"
    assert parse_http(text)[0]["body"] == "line1\n\nline3"


def test_body_may_contain_lines_with_hashes_and_slashes():
    text = "POST http://x\n\n# not a comment\n// nor this\n"
    assert parse_http(text)[0]["body"] == "# not a comment\n// nor this"


def test_line_numbers_are_recorded():
    reqs = parse_http(DOC)
    assert reqs[0]["line"] == 6
    assert reqs[1]["line"] == 18


def test_crlf_line_endings():
    text = "GET http://x\r\nAccept: a\r\n\r\nbody\r\n"
    r = parse_http(text)[0]
    assert r["headers"] == {"Accept": "a"} and r["body"] == "body"


@pytest.mark.parametrize(
    "text, fragment, line",
    [
        ("FETCH http://x\n", "expected a request line", 1),
        ("hello\n", "expected a request line", 1),
        ("GET http://x\nnot a header\n", "expected a header", 2),
        ("GET http://x\n\n> assert status ==\n", "needs a value", 3),
        ("GET http://x\n\n> capture token\n", "bad capture", 3),
        ("GET http://x\n\n> log hi\n", "unknown directive", 3),
        ("### a\nGET http://x\n\n###\nBOGUS\n", "expected a request line", 5),
    ],
)
def test_parse_errors_carry_line_numbers(text, fragment, line):
    with pytest.raises(ParseError) as exc:
        parse_http_document(text, source="api.http")
    assert fragment in exc.value.message
    assert exc.value.line == line
    assert str(exc.value).startswith(f"api.http:{line}:")


def test_sections_with_only_comments_and_variables_are_skipped():
    assert parse_http("### only a title\n\n###\n# note\n@x = 1\n") == []
