from curlbook.subst import substitute


def test_substitute_basic():
    assert substitute("Hello {{name}}", {"name": "World"}) == "Hello World"


def test_substitute_multiple():
    text = "{{a}}-{{b}}-{{a}}"
    assert substitute(text, {"a": "1", "b": "2"}) == "1-2-1"


def test_substitute_whitespace():
    assert substitute("{{ name }}", {"name": "x"}) == "x"


def test_substitute_unknown_left_unchanged():
    assert substitute("{{missing}}", {}) == "{{missing}}"


def test_substitute_non_string_value():
    assert substitute("n={{n}}", {"n": 42}) == "n=42"