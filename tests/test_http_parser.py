from curlbook.http_parser import parse_http


def test_parse_http_simple():
    text = """GET https://example.com
Accept: application/json
Content-Type: application/json

{"key": "value"}
"""
    requests = parse_http(text)
    assert len(requests) == 1
    req = requests[0]
    assert req["method"] == "GET"
    assert req["url"] == "https://example.com"
    assert req["headers"] == {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    assert req["body"] == '{"key": "value"}'


def test_parse_http_multiple_requests():
    text = """GET https://example.com
Accept: application/json

###
POST https://example.com/api
Content-Type: text/plain

hello
"""
    requests = parse_http(text)
    assert len(requests) == 2
    # First request
    assert requests[0]["method"] == "GET"
    assert requests[0]["url"] == "https://example.com"
    assert requests[0]["headers"] == {"Accept": "application/json"}
    assert requests[0]["body"] == ""
    # Second request
    assert requests[1]["method"] == "POST"
    assert requests[1]["url"] == "https://example.com/api"
    assert requests[1]["headers"] == {"Content-Type": "text/plain"}
    assert requests[1]["body"] == "hello"


def test_parse_http_empty():
    text = ""
    assert parse_http(text) == []


def test_parse_http_only_whitespace_and_comments():
    text = "\n\n### comment\n\n"
    assert parse_http(text) == []