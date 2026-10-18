import re

import pytest

from curlbook.subst import substitute, substitute_all, variables_in


def test_process_environment_variable(monkeypatch):
    monkeypatch.setenv("CURLBOOK_TEST_TOKEN", "s3cret")
    assert substitute("Bearer {{ $env.CURLBOOK_TEST_TOKEN }}", {}) == "Bearer s3cret"


def test_missing_process_environment_variable_names_the_placeholder(monkeypatch):
    monkeypatch.delenv("CURLBOOK_NOPE", raising=False)
    with pytest.raises(KeyError) as exc:
        substitute("{{$env.CURLBOOK_NOPE}}", {})
    assert exc.value.args[0] == "$env.CURLBOOK_NOPE"


def test_uuid_is_fresh_each_time():
    a, b = substitute("{{$uuid}}", {}), substitute("{{$uuid}}", {})
    assert re.fullmatch(r"[0-9a-f-]{36}", a) and a != b


def test_timestamp_and_random_int():
    assert substitute("{{$timestamp}}", {}).isdigit()
    assert 0 <= int(substitute("{{$randomInt}}", {})) <= 999
    assert "T" in substitute("{{$isoTimestamp}}", {})


def test_unknown_dynamic_variable():
    with pytest.raises(KeyError):
        substitute("{{$nonsense}}", {})


def test_dotted_and_dashed_names():
    env = {"user.name": "raj", "api-key": "k"}
    assert substitute("{{user.name}} {{ api-key }}", env) == "raj k"


def test_json_braces_are_left_alone():
    text = '{"a": {"b": 1}, "c": {{x}}}'
    assert substitute(text, {"x": 2}) == '{"a": {"b": 1}, "c": 2}'
    assert substitute('{"a": {"b": {"c": 1}}}', {}) == '{"a": {"b": {"c": 1}}}'


def test_value_containing_braces_is_not_resubstituted():
    assert substitute("{{a}}", {"a": "{{b}}", "b": "no"}) == "{{b}}"


def test_name_cannot_start_with_digit():
    assert substitute("{{1abc}}", {}) == "{{1abc}}"


def test_variables_in_lists_unique_names_in_order():
    assert variables_in("{{b}} {{a}} {{b}} {{$env.X}}") == ["b", "a", "$env.X"]


def test_substitute_all_walks_nested_structures():
    data = {"{{k}}": ["{{v}}", {"n": 1, "s": "x{{v}}"}], "plain": 3}
    assert substitute_all(data, {"k": "key", "v": "val"}) == {
        "key": ["val", {"n": 1, "s": "xval"}],
        "plain": 3,
    }


def test_non_string_values_render_as_json():
    env = {"t": True, "f": False, "n": None, "l": [1, "a"], "o": {"k": 1}, "i": 3, "x": 1.5}
    text = "{{t}} {{f}} {{n}} {{l}} {{o}} {{i}} {{x}}"
    assert substitute(text, env) == 'true false null [1, "a"] {"k": 1} 3 1.5'
