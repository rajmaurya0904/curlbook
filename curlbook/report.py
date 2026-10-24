"""Render run results as text, JSON or JUnit XML."""

from __future__ import annotations

import json
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from .engine import RequestResult


@dataclass
class FileRun:
    """The results of running one collection file."""

    path: str
    results: list[RequestResult]

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed and not r.skipped)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.skipped)


def totals(runs: list[FileRun]) -> tuple[int, int, int]:
    return (
        sum(r.passed for r in runs),
        sum(r.failed for r in runs),
        sum(r.skipped for r in runs),
    )


def summary_line(runs: list[FileRun]) -> str:
    passed, failed, skipped = totals(runs)
    line = f"Passed: {passed}, Failed: {failed}"
    return line + (f", Skipped: {skipped}" if skipped else "")


def result_line(res: RequestResult, color=None) -> str:
    """``PASS  GET http://... 200 12ms  name`` for one request."""
    tag = "SKIP" if res.skipped else ("PASS" if res.passed else "FAIL")
    if color:
        tag = color(tag, {"PASS": "green", "FAIL": "red", "SKIP": "yellow"}[tag])
    status = str(res.status) if res.status is not None else "---"
    timing = f"{res.elapsed_ms:.0f}ms" if res.elapsed_ms is not None else ""
    parts = [tag, f"{res.index:>2}", res.method, res.url, status, timing]
    line = " ".join(p for p in parts if p)
    if res.name and res.name != f"{res.method} {res.url}":
        line += f"  ({res.name})"
    return line


def render_text(runs: list[FileRun], color=None) -> str:
    lines: list[str] = []
    for run in runs:
        if len(runs) > 1:
            lines.append(f"== {run.path}")
        for res in run.results:
            lines.append(result_line(res, color))
            for failure in res.failures:
                lines.append(f"       {failure}")
    lines.append("")
    lines.append(summary_line(runs))
    return "\n".join(lines)


def _result_dict(res: RequestResult) -> dict:
    return {
        "index": res.index,
        "name": res.name,
        "method": res.method,
        "url": res.url,
        "status": res.status,
        "elapsed_ms": res.elapsed_ms,
        "passed": res.passed,
        "skipped": res.skipped,
        "error": res.error,
        "assertions": [
            {"assertion": o.text, "ok": o.ok, "message": o.message} for o in res.outcomes
        ],
        "captured": sorted(res.captured),
    }


def render_json(runs: list[FileRun]) -> str:
    """Machine-readable report. Captured values are listed by name only, not value,
    so tokens do not end up in CI logs."""
    passed, failed, skipped = totals(runs)
    doc = {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "ok": failed == 0,
        "files": [
            {"file": run.path, "results": [_result_dict(r) for r in run.results]} for run in runs
        ],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False)


def render_junit(runs: list[FileRun]) -> str:
    """JUnit XML: one testsuite per file, one testcase per request."""
    passed, failed, skipped = totals(runs)
    root = ET.Element(
        "testsuites",
        name="curlbook",
        tests=str(passed + failed + skipped),
        failures=str(failed),
        skipped=str(skipped),
    )
    for run in runs:
        suite = ET.SubElement(
            root,
            "testsuite",
            name=run.path,
            tests=str(len(run.results)),
            failures=str(run.failed),
            skipped=str(run.skipped),
        )
        for res in run.results:
            case = ET.SubElement(
                suite,
                "testcase",
                classname=run.path,
                name=f"{res.index}. {res.name}",
                time=f"{(res.elapsed_ms or 0) / 1000:.3f}",
            )
            if res.skipped:
                ET.SubElement(case, "skipped", message="earlier request failed (--fail-fast)")
            elif not res.passed:
                failure = ET.SubElement(
                    case, "failure", message=res.failures[0] if res.failures else "failed"
                )
                failure.text = "\n".join(res.failures)
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")
