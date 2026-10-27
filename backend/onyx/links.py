"""Wikilinks: finding [[links]] in notes and resolving them to notes.

A link is written [[Target]], [[Target|shown text]], [[Target#Heading]] or
[[Folder/Target]]. Like Obsidian, a target names a file, not a title:
"Atlas kickoff" finds "Projects/Atlas kickoff.md". When several files have
that name, the one in the linking note's own folder wins, then the shortest
path, then the first alphabetically. A target with a "/" must match the
path's end exactly. Matching ignores case.

Links inside code (``` fences and `inline code`) aren't links. Links in a
task's `projects` frontmatter are links too (TaskNotes style).

Nothing here touches the disk.
"""

import re
from pathlib import PurePosixPath

MAX_TARGET_CHARS = 300

_WIKILINK = re.compile(r"\[\[([^\[\]\n]{1,300})\]\]")
_FENCE = re.compile(r"^(```|~~~)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")


def target_of(raw: str) -> str:
    """The file part of a link: "Note#Heading|Text" → "Note"."""
    return raw.split("|", 1)[0].split("#", 1)[0].strip()


def find_links(body: str) -> list[str]:
    """The link targets in a note's body, in order, without code."""
    found: list[str] = []
    in_fence = False
    for line in body.split("\n"):
        if _FENCE.match(line.lstrip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in _WIKILINK.finditer(_INLINE_CODE.sub("", line)):
            target = target_of(match.group(1))
            if target:
                found.append(target)
    return found


def link_from_value(value: str) -> str | None:
    """A frontmatter value like "[[Atlas architecture]]" → "Atlas architecture"."""
    text = value.strip()
    if text.startswith("[[") and text.endswith("]]"):
        return target_of(text[2:-2]) or None
    return None


class LinkIndex:
    """Resolves link targets against every note path in the vault."""

    def __init__(self, paths: list[str]) -> None:
        self._by_name: dict[str, list[str]] = {}
        self._paths = sorted(paths)
        for path in self._paths:
            stem = PurePosixPath(path).stem.lower()
            self._by_name.setdefault(stem, []).append(path)

    def resolve(self, target: str, from_path: str) -> str | None:
        target = target.strip().removesuffix(".md")
        if not target or len(target) > MAX_TARGET_CHARS:
            return None
        name = PurePosixPath(target).name.lower()
        candidates = self._by_name.get(name, [])
        if "/" in target:
            wanted = f"{target.lower()}.md"
            candidates = [
                p for p in candidates if p.lower() == wanted or p.lower().endswith(f"/{wanted}")
            ]
        if not candidates:
            return None
        here = str(PurePosixPath(from_path).parent)
        return min(
            candidates,
            key=lambda p: (str(PurePosixPath(p).parent) != here, p.count("/"), len(p), p),
        )
