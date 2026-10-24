"""The ``curlbook`` command: run, list, check and import."""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path
from typing import Any

import click

from . import __version__
from .engine import resolve_variables, run_collection
from .env_loader import load_env, parse_assignments
from .errors import CurlbookError
from .loader import expand_paths, load_collection
from .model import Collection, Request, display_name
from .report import FileRun, render_json, render_junit, render_text, result_line, summary_line

EXIT_FAILED = 1
EXIT_BAD_INPUT = 2


def _fail(message: str) -> None:
    click.echo(f"curlbook: {message}", err=True)
    sys.exit(EXIT_BAD_INPUT)


def _guard(fn):
    """Turn expected errors into one-line messages and exit code 2."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except CurlbookError as exc:
            _fail(str(exc))

    return wrapper


def build_env(collection: Collection, env_files: tuple[str, ...], var: tuple[str, ...]) -> dict:
    """File variables, then ``--env`` files in order, then ``--var`` overrides."""
    given: dict[str, Any] = {}
    for path in env_files:
        given.update(load_env(path))
    given.update(parse_assignments(var))
    env = dict(resolve_variables(collection.variables, given))
    env.update(given)
    return env


def select_requests(requests: list[Request], only: tuple[str, ...]) -> list[Request]:
    """Keep requests matching any ``--only``: a 1-based index or a name substring."""
    if not only:
        return requests
    keep: list[Request] = []
    for i, req in enumerate(requests, start=1):
        label = display_name(req).lower()
        if any(o == str(i) or o.lower() in label for o in only):
            keep.append(req)
    if not keep:
        raise CurlbookError(f"--only {', '.join(only)} matched no request")
    return keep


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="curlbook")
def main() -> None:
    """Plain-text API request collections that run from the terminal and CI.

    Collections are .http or .yaml files; see `curlbook run --help`.
    Exit codes: 0 all passed, 1 a request failed, 2 bad input (missing file,
    parse error, bad option).
    """


@main.command()
@click.argument("files", nargs=-1, required=True, metavar="FILE...")
@click.option("-e", "--env", "env_files", multiple=True, metavar="FILE",
              help="Variables from a .json, .yaml or .env file. Repeatable; later files win.")
@click.option("-v", "--var", multiple=True, metavar="NAME=VALUE",
              help="Set one variable; beats --env files. Repeatable.")
@click.option("-f", "--format", "fmt", type=click.Choice(["text", "json", "junit"]),
              default="text", show_default=True, help="Report format.")
@click.option("-o", "--output", type=click.Path(dir_okay=False), help="Write the report to a file.")
@click.option("--fail-fast", is_flag=True, help="Stop at the first failing request.")
@click.option("--only", multiple=True, metavar="N|TEXT",
              help="Run only requests with this number or name containing TEXT. Repeatable.")
@click.option("--timeout", type=float, default=30.0, show_default=True, metavar="SECONDS")
@click.option("--insecure", is_flag=True, help="Do not verify TLS certificates.")
@click.option("--no-color", is_flag=True, help="Plain text even on a terminal.")
@_guard
def run(files, env_files, var, fmt, output, fail_fast, only, timeout, insecure, no_color) -> None:
    """Run the requests in the given files and check their assertions."""
    if timeout <= 0:
        raise click.UsageError("--timeout must be positive")
    paths = expand_paths(list(files))
    stream = fmt == "text" and not output
    use_color = stream and not no_color and sys.stdout.isatty()
    color = (lambda text, fg: click.style(text, fg=fg)) if use_color else None

    runs: list[FileRun] = []
    for path in paths:
        collection = load_collection(path)
        env = build_env(collection, env_files, var)
        requests = select_requests(collection.requests, only)
        if stream:
            if len(paths) > 1:
                click.echo(f"== {path}")
            callback = _printer(color)
        else:
            callback = None
        results = run_collection(
            requests, env, fail_fast=fail_fast, timeout=timeout, verify=not insecure,
            on_result=callback,
        )
        runs.append(FileRun(str(path), results))

    if stream:
        click.echo("")
        click.echo(summary_line(runs))
    else:
        text = {"text": lambda r: render_text(r), "json": render_json, "junit": render_junit}[fmt](
            runs
        )
        if output:
            Path(output).write_text(text + "\n", encoding="utf-8", newline="\n")
            click.echo(summary_line(runs), err=True)
        else:
            click.echo(text)
    sys.exit(EXIT_FAILED if any(r.failed for r in runs) else 0)


def _printer(color):
    def show(res) -> None:
        click.echo(result_line(res, color))
        for failure in res.failures:
            click.echo(f"       {failure}")

    return show


@main.command("list")
@click.argument("file")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@_guard
def list_cmd(file: str, as_json: bool) -> None:
    """Print the numbered requests in FILE without sending anything."""
    collection = load_collection(file)
    if as_json:
        click.echo(json.dumps(
            [{"index": i, "name": r["name"], "method": r["method"], "url": r["url"],
              "asserts": len(r["asserts"]), "captures": len(r["captures"])}
             for i, r in enumerate(collection.requests, start=1)], indent=2))
        return
    if not collection.requests:
        click.echo("No requests found")
        return
    width = len(str(len(collection.requests)))
    for i, req in enumerate(collection.requests, start=1):
        extra = []
        if req["captures"]:
            extra.append(f"{len(req['captures'])} capture{'s' * (len(req['captures']) != 1)}")
        if req["asserts"]:
            extra.append(f"{len(req['asserts'])} assert{'s' * (len(req['asserts']) != 1)}")
        label = f"  ({req['name']})" if req["name"] else ""
        tail = f"  [{', '.join(extra)}]" if extra else ""
        click.echo(f"{i:>{width}}  {req['method']:<6} {req['url']}{label}{tail}")


@main.command()
@click.argument("files", nargs=-1, required=True, metavar="FILE...")
@_guard
def check(files) -> None:
    """Parse the given files and report syntax errors; sends nothing."""
    bad = 0
    for path in expand_paths(list(files)):
        try:
            collection = load_collection(path)
        except CurlbookError as exc:
            click.echo(f"FAIL {exc}", err=True)
            bad += 1
            continue
        n = len(collection.requests)
        click.echo(f"ok   {path}: {n} request{'s' * (n != 1)}")
    sys.exit(EXIT_BAD_INPUT if bad else 0)


@main.command("import")
@click.argument("source", type=click.Path(dir_okay=False))
@click.option("-f", "--format", "fmt", type=click.Choice(["http", "yaml"]), default="http",
              show_default=True, help="Output collection format.")
@click.option("-o", "--output", type=click.Path(dir_okay=False),
              help="Write to this file (default: stdout).")
@click.option("--env-out", type=click.Path(dir_okay=False),
              help="Also write the collection's variables as a JSON environment file.")
@_guard
def import_cmd(source: str, fmt: str, output: str | None, env_out: str | None) -> None:
    """Convert a Postman collection (v2.0/v2.1) or environment export."""
    from .postman import import_postman_file
    from .writers import to_http, to_yaml

    imported = import_postman_file(source)
    text = (to_http if fmt == "http" else to_yaml)(imported.collection)
    if output:
        Path(output).write_text(text, encoding="utf-8", newline="\n")
        n = len(imported.collection.requests)
        click.echo(f"Wrote {output} ({n} request{'s' * (n != 1)})", err=True)
    else:
        click.echo(text, nl=False)
    if env_out:
        Path(env_out).write_text(
            json.dumps(imported.collection.variables, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        click.echo(f"Wrote {env_out}", err=True)
    for warning in imported.warnings:
        click.echo(f"warning: {warning}", err=True)


if __name__ == "__main__":
    main()
