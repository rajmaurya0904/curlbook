# Curlbook

Plain-text .http/YAML request collections with environments, chaining and assertions, runnable from the terminal and CI, with a Postman collection importer. For people who want a minimal Postman alternative that lives in git.

## Installation

```bash
pip install curlbook
```

## Usage

Run a collection of HTTP requests defined in a `.http` or `.yaml` file:

```bash
curlbook run samples/example.http
```

### Environment files

You can supply an environment file (JSON or YAML) to substitute variables in the request definitions:

```bash
curlbook run --env dev.env.yaml samples/example.http
```

Inside the request files use `{{ VAR_NAME }}` placeholders which will be replaced by values from the environment file.

### Chaining requests

Requests can reference the response of previous requests using the `{{ previous.response.json.key }}` syntax. For example, to use an ID returned from a login request in a subsequent request:

```http
### login.http
POST https://api.example.com/login
Content-Type: application/json

{"username": "{{ USER }}}", "password": "{{ PASS }}}"}

### get_user.http
GET https://api.example.com/users/{{ login.response.json.id }}
Authorization: Bearer {{ login.response.json.token }}
```

Running the file will execute `login` first, then substitute the returned `id` and `token` into the `get_user` request.

### Assertions

Add assertions to verify responses. Prefix a line with `> assert` followed by a Python expression that evaluates to `True`:

```http
GET https://api.example.com/status
> assert response.status_code == 200
> assert response.json()['status'] == 'ok'
```

If any assertion fails, `curlbook` will exit with a non‑zero status and report the failure.
```

## Example

TODO.

## FAQ

TODO.

## License

MIT -- see [LICENSE](LICENSE).
