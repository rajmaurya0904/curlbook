"""Exception types shared across curlbook."""

from __future__ import annotations


class CurlbookError(Exception):
    """Base class for errors that should be shown to the user without a traceback."""


class ParseError(CurlbookError):
    """A collection, directive or path expression could not be understood."""

    def __init__(self, message: str, line: int | None = None, source: str | None = None):
        self.message = message
        self.line = line
        self.source = source
        super().__init__(self._format())

    def _format(self) -> str:
        where = ""
        if self.source and self.line:
            where = f"{self.source}:{self.line}: "
        elif self.line:
            where = f"line {self.line}: "
        elif self.source:
            where = f"{self.source}: "
        return f"{where}{self.message}"


class EnvError(CurlbookError):
    """An environment file could not be read or understood."""
