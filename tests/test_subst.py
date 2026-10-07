from curlbook.subst import substitute


def test_substitute_basic():
    assert substitute("Hello {{name}}", {"name": "World"}) == "Hello World"


def test_substitute_multiple():
    text = "{{a}}-{{b}}-{{a}}"
    assert substitute(text, {"a": "1", "b": "2"}) == "1-2-1"


def test_substitute_whitespace():
    assert substitute("{{ name }}", {"name": "x"}) == "x"


def test_substitute_unknown_raises():
    try:
        substitute("{{missing}}", {})
    except KeyError as e:
        assert e.args[0] == "missing"
    else:
        raise AssertionError("Expected KeyError")


def test_substitute_non_string_value():
    assert substitute("n={{n}}", {"n": 42}) == "n=42"