"""Reading a note's YAML frontmatter and its Markdown sections.

Frontmatter is the block between a first line of "---" and the next "---".
It's parsed with yaml.safe_load only (no Python objects can be built from a
note), and only if it's at most MAX_FRONTMATTER_BYTES. Anything that isn't a
mapping, doesn't parse or is too big gives {}: a broken note still lists,
it just has no fields.

Nothing here touches the disk; callers pass in text read through onyx.vault.
"""

import re

import yaml

MAX_FRONTMATTER_BYTES = 64 * 1024

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def split(text: str) -> tuple[dict, str]:
    """Return (frontmatter, body). Body is the text after the frontmatter."""
    text = text.removeprefix("﻿")
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r") == "---":
            raw = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            return _parse(raw), body
    return {}, text  # no closing line: not frontmatter


def _parse(raw: str) -> dict:
    if len(raw.encode("utf-8")) > MAX_FRONTMATTER_BYTES:
        return {}
    try:
        data = yaml.safe_load(raw)
    except (yaml.YAMLError, RecursionError):
        # RecursionError: deeply nested YAML ("[[[[…") fits in a few KB.
        return {}
    return data if isinstance(data, dict) else {}


def first_heading(body: str) -> str | None:
    """The text of the first level-1 heading, if there is one."""
    for line in body.split("\n"):
        match = _HEADING.match(line.rstrip("\r"))
        if match and len(match.group(1)) == 1 and match.group(2):
            return match.group(2)
    return None


def section(body: str, title: str) -> list[str]:
    """The lines under a heading with this exact title (any level), up to the
    next heading of the same or a higher level. Empty if there's no such heading.
    Used for "Status History" now, and for "Context" later."""
    lines = body.split("\n")
    for index, line in enumerate(lines):
        match = _HEADING.match(line.rstrip("\r"))
        if not match or match.group(2) != title:
            continue
        level = len(match.group(1))
        found = []
        for following in lines[index + 1 :]:
            next_heading = _HEADING.match(following.rstrip("\r"))
            if next_heading and len(next_heading.group(1)) <= level:
                break
            found.append(following.rstrip("\r"))
        return found
    return []
