"""Environment variable substitution for curlbook."""

import re

_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def substitute(text, env):
    """Replace ``{{ var }}`` placeholders in *text* with values from *env*.

    Unknown variables are left unchanged.
    """

    def _replace(match):
        name = match.group(1)
        if name in env:
            return str(env[name])
        return match.group(0)

    return _VAR_RE.sub(_replace, text)