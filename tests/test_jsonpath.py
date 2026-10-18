import pytest

from curlbook.errors import ParseError
from curlbook.jsonpath import PathMissing, extract, lookup, parse_path

DOC = {
    "token": "abc",
    "user": {"id": 7, "tags": ["a", "b", "c"], "x-y": True},
    "items": [{"id": 1, "n": "one"}, {"id": 2, "n": "two"}],
    "nothing": None,
}


def test_root_returns_document():
    assert extract(DOC, "$") is DOC


def test_dotted_keys():
    assert extract(DOC, "$.token") == "abc"
    assert extract(DOC, "$.user.id") == 7


def test_index_and_negative_index():
    assert extract(DOC, "$.user.tags[0]") == "a"
    assert extract(DOC, "$.user.tags[-1]") == "c"


def test_bracket_names_allow_odd_keys():
    assert extract(DOC, "$['user']['x-y']") is True
    assert extract({"a b": 1}, '$["a b"]') == 1


def test_wildcard_collects_all_matches():
    assert extract(DOC, "$.items[*].id") == [1, 2]
    assert extract(DOC, "$.items.*.n") == ["one", "two"]


def test_wildcard_with_no_matches_is_empty_list_not_missing():
    assert lookup(DOC, "$.items[*].zzz") == (True, [])


def test_null_value_is_found():
    assert lookup(DOC, "$.nothing") == (True, None)


def test_missing_key_and_out_of_range():
    assert lookup(DOC, "$.nope") == (False, None)
    assert lookup(DOC, "$.user.tags[9]") == (False, None)
    with pytest.raises(PathMissing):
        extract(DOC, "$.user.tags[9]")


def test_type_mismatch_is_just_missing():
    assert lookup(DOC, "$.token.id") == (False, None)
    assert lookup(DOC, "$.user[0]") == (False, None)


@pytest.mark.parametrize("bad", ["token", "$.", "$..a", "$[abc]", "$[1", "$.a b"])
def test_bad_paths_raise_parse_error(bad):
    with pytest.raises(ParseError):
        parse_path(bad)
