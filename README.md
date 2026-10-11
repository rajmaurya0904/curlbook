# curlbook

**Turns a plain-text `.http` file of API requests into structured request dictionaries, with `{{VAR}}` placeholders filled in from an environment dict.**

**Status: early and incomplete.** Two pieces work and are tested — the `.http`
parser and the variable substituter. Everything else the name implies is **not
implemented**: there is no `curlbook` command, nothing sends a request, and there is
no chaining, no assertions, no YAML collections and no Postman importer. Today this
is a parsing library, not a runner.

## The problem

API request collections live in a GUI, which means they live outside git: no diffs,
no review, no "why did this header change in March". A `.http` file next to the code
fixes that, but then something has to read it. curlbook is that reader — the small,
dull half of the job that a request runner would sit on top of.

## Real output

`api.http`, two requests separated by `###`, with `{{VAR}}` placeholders:

```http
POST {{BASE}}/login
Content-Type: application/json

{"user": "{{USER}}"}

###
GET {{BASE}}/users/me
Authorization: Bearer {{TOKEN}}
```

Substitute an environment, then parse:

```console
$ python show.py
[
  {
    "method": "POST",
    "url": "https://api.example.com/login",
    "headers": {
      "Content-Type": "application/json"
    },
    "body": "{\"user\": \"raj\"}"
  },
  {
    "method": "GET",
    "url": "https://api.example.com/users/me",
    "headers": {
      "Authorization": "Bearer t0ken"
    },
    "body": ""
  }
]
```

`show.py` is the script that printed that:

```python
import json

from curlbook.http_parser import parse_http
from curlbook.subst import substitute

env = {"BASE": "https://api.example.com", "USER": "raj", "TOKEN": "t0ken"}
raw = open("api.http").read()
print(json.dumps(parse_http(substitute(raw, env)), indent=2))
```

## Install

Not on PyPI. Clone it and install from the working tree:

```bash
pip install -e ".[dev]"
```

## Usage

There is no command line. Two functions:

```python
parse_http(text)          # -> [{"method", "url", "headers", "body"}, ...]
substitute(text, env)      # fills {{VAR}}; raises KeyError on an unknown name
```

Substitute first, then parse — the placeholders are plain text, so order only matters
if a variable's value could itself contain a `###` line.

## How it works

| Step | What happens |
| --- | --- |
| Split | The text is cut on any line whose stripped form starts with `###`. Anything else on that line is dropped. |
| Request line | The first line of each section is split on whitespace; field 1 is the method, field 2 is the URL. Fewer than two fields and the section is skipped silently. |
| Headers | Following lines are split on the first `:` into key/value, both stripped, until the first blank line. |
| Body | Everything after that blank line, joined with `\n`. No blank line means no body. |
| Variables | `{{ NAME }}` matches `[A-Za-z_][A-Za-z0-9_]*` with optional inner whitespace. Values are coerced with `str()`. |

## Limitations

- **Nothing is sent.** `requests`, `click` and `pyyaml` are declared as dependencies
  but no module imports them.
- No CLI, so no `curlbook run`, no `--env` flag, no CI exit codes.
- No request chaining. `{{ login.response.json.id }}` is not special — the dot makes
  it fail the variable pattern, so it is left in the text verbatim.
- No `> assert` lines. They would be parsed as part of the body.
- No YAML collections and no Postman importer.
- Request names after `###` are discarded, so parsed requests are positional only.
- A malformed request line is skipped with no error, which can silently shrink the
  list you get back.
- Header names are not deduplicated or case-folded; repeats overwrite.

## Development

```bash
pip install -e ".[dev]"
pytest -q        # 10 tests
ruff check .
```

MIT — see [LICENSE](LICENSE).
