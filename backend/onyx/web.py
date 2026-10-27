"""Serving the built frontend (frontend/dist) under the strict CSP.

index.html is generated per request: a fresh random nonce goes into the
page's <meta name="csp-nonce"> and into that response's CSP header as
style-src 'self' 'nonce-…'. Radix tags the few <style> elements it creates
with that nonce (see frontend/src/nonce.ts); every other inline style or
script is still blocked (threat model T6). API responses keep style-src
'self' with no nonce.

Other files are served only from a list of dist's regular files made at
startup (no hidden files, no symlinks); a request path is only a key into
it. Any other non-API path gets index.html, so the app's own routes work on
reload. /api/* paths never fall through to it.
"""

import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

NONCE_PLACEHOLDER = "__CSP_NONCE__"


def new_nonce() -> str:
    return secrets.token_urlsafe(16)  # 128 bits, URL-safe characters only


def mount_frontend(app: FastAPI, dist: Path) -> None:
    dist_real = Path(os.path.realpath(dist))
    index_file = dist_real / "index.html"
    template = index_file.read_text(encoding="utf-8") if index_file.is_file() else None
    if template is not None and template.count(NONCE_PLACEHOLDER) != 1:
        raise RuntimeError("frontend/dist/index.html must contain the nonce placeholder once")

    def index(request: Request) -> Response:
        if template is None:
            return HTMLResponse(
                "<!doctype html><title>Onyx Sheiko</title>"
                "<p>The frontend isn't built yet: run <code>npm run build</code> in frontend/.</p>",
                status_code=503,
            )
        nonce = new_nonce()
        request.state.csp_nonce = nonce  # read by SecurityHeaders for this response
        html = template.replace(NONCE_PLACEHOLDER, nonce)
        # A new nonce every time, so the page must never be cached.
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    # Every servable file, listed once at startup. A request path is only ever
    # used as a key into this table, never to build a file path, so no URL can
    # reach a file outside it (CodeQL py/path-injection). Rebuilt files need a
    # server restart, as does a new index.html.
    files = _servable_files(dist_real, index_file) if template is not None else {}

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str, request: Request) -> Response:
        if path == "api" or path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        file = files.get(path)
        if file is not None:
            return FileResponse(file)
        return index(request)


def _servable_files(dist_real: Path, index_file: Path) -> dict[str, Path]:
    """Regular files inside dist, by relative path. Skips hidden files and
    folders, symlinks, and index.html (always generated per request)."""
    found: dict[str, Path] = {}
    for folder, dirs, names in os.walk(dist_real, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in names:
            full = Path(folder, name)
            if name.startswith(".") or full.is_symlink() or not full.is_file():
                continue
            if full == index_file:
                continue
            found[full.relative_to(dist_real).as_posix()] = full
    return found
