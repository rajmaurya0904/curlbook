from __future__ import annotations

from pathlib import Path

import pytest

from curlbook.env_loader import load_env, parse_assignments, parse_dotenv
from curlbook.errors import EnvError


def write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_json_env(tmp_path: Path) -> None:
    assert load_env(write(tmp_path, "e.json", '{"a": 1, "b": "x"}')) == {"a": 1, "b": "x"}


def test_yaml_env(tmp_path: Path) -> None:
    env = load_env(write(tmp_path, "e.yaml", "base: http://h\nretries: 3\n"))
    assert env == {"base": "http://h", "retries": 3}


def test_yml_extension(tmp_path: Path) -> None:
    assert load_env(write(tmp_path, "e.yml", "a: b")) == {"a": "b"}


def test_dotenv_file(tmp_path: Path) -> None:
    text = "\n".join(
        [
            "# comment",
            "TOKEN=abc",
            "",
            "export NAME='Raj M'",
            r'Q="say \"hi\""',
            "URL=http://x # trailing",
        ]
    )
    env = load_env(write(tmp_path, ".env", text))
    assert env == {"TOKEN": "abc", "NAME": "Raj M", "Q": 'say "hi"', "URL": "http://x"}


def test_dotenv_with_other_name(tmp_path: Path) -> None:
    assert load_env(write(tmp_path, "prod.env", "A=1")) == {"A": "1"}


def test_bom_is_tolerated(tmp_path: Path) -> None:
    p = tmp_path / "e.json"
    p.write_bytes(b'\xef\xbb\xbf{"a": 1}')
    assert load_env(p) == {"a": 1}


def test_empty_yaml_is_empty_env(tmp_path: Path) -> None:
    assert load_env(write(tmp_path, "e.yaml", "")) == {}


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(EnvError, match="not found"):
        load_env(tmp_path / "nope.json")


def test_invalid_json(tmp_path: Path) -> None:
    with pytest.raises(EnvError, match="invalid JSON"):
        load_env(write(tmp_path, "e.json", "{oops"))


def test_json_list_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(EnvError, match="mapping"):
        load_env(write(tmp_path, "e.json", "[1, 2]"))


def test_invalid_yaml(tmp_path: Path) -> None:
    with pytest.raises(EnvError, match="invalid YAML"):
        load_env(write(tmp_path, "e.yaml", "a: [unclosed"))


def test_dotenv_error_names_the_line() -> None:
    with pytest.raises(EnvError, match=r"\.env:2: expected KEY=value"):
        parse_dotenv("A=1\nthis is not valid\n")


def test_assignments() -> None:
    assert parse_assignments(["a=1", "b=x=y"]) == {"a": "1", "b": "x=y"}


@pytest.mark.parametrize("bad", ["novalue", "=x"])
def test_bad_assignment(bad: str) -> None:
    with pytest.raises(EnvError, match="NAME=VALUE"):
        parse_assignments([bad])
