"""The FastAPI app. Build one with create_app(settings) per server run."""

from datetime import date

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from onyx import config, editing, models, summary
from onyx.auth import SESSION_COOKIE, AuthState
from onyx.cache import NoteCache, default_cache_dir
from onyx.config import Settings
from onyx.security import ApiGuard, BodySizeLimit, SecurityHeaders, session_from_scope
from onyx.vault import NoteNotFound, Vault, VersionConflict
from onyx.web import mount_frontend


class LaunchCode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=128)


class SaveNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=512)
    body: str = Field(max_length=config.MAX_BODY_BYTES)
    version: str = Field(pattern=r"^[0-9a-f]{64}$", description="The version the editor opened")


def create_app(settings: Settings) -> FastAPI:
    auth = AuthState(settings.launch_code_ttl, settings.session_ttl)
    vault = Vault(settings.vault)
    # The cache is rebuilt from the files on every start (threat model T10).
    cache = NoteCache(vault, settings.cache_dir or default_cache_dir())
    cache.rebuild()

    # No interactive docs: they load scripts from a CDN, which the CSP forbids,
    # and the schema is generated at build time instead of being served.
    app = FastAPI(title="Onyx Sheiko", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.auth = auth
    app.state.vault = vault
    app.state.cache = cache

    @app.post(
        "/api/session",
        status_code=204,
        responses={401: {"model": models.ErrorResponse, "description": "Wrong or used code"}},
    )
    def sign_in(body: LaunchCode) -> Response:
        session = auth.redeem_launch_code(body.code)
        if session is None:
            return JSONResponse({"detail": "Invalid or expired launch code"}, status_code=401)
        response = Response(status_code=204)
        response.set_cookie(
            SESSION_COOKIE,
            session,
            max_age=settings.session_ttl,
            path="/",
            httponly=True,
            samesite="strict",
            # Plain http on 127.0.0.1. Must become True if the app is ever
            # served over HTTPS (going beyond localhost needs its own review).
            secure=False,
        )
        return response

    @app.get("/api/session", response_model=models.SessionStatus)
    def session_status(request: Request) -> dict[str, bool]:
        return {"authenticated": auth.is_valid_session(session_from_scope(request.scope))}

    @app.delete("/api/session", status_code=204)
    def sign_out(request: Request) -> Response:
        auth.end_session(session_from_scope(request.scope))
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")
        return response

    def today() -> date:
        return settings.today or date.today()

    # Read-only summaries. Each request reads the files again, so Home is never
    # stale; the cache will take this over when the vault gets large.
    @app.get("/api/home", response_model=models.HomeData)
    def home() -> dict:
        return summary.home(summary.read_summary(vault), today())

    @app.get("/api/items", response_model=models.ItemList)
    def items() -> dict:
        return {"items": summary.items(summary.read_summary(vault))}

    @app.get("/api/search", response_model=models.SearchResults)
    def search(q: str = Query(min_length=1, max_length=200)) -> dict:
        return {"results": cache.search(q)}

    @app.get("/api/notes", response_model=models.NoteList)
    def notes() -> dict:
        return {"notes": summary.notes_list(summary.read_summary(vault))}

    @app.get(
        "/api/note",
        response_model=models.NoteDetail,
        responses={404: {"model": models.ErrorResponse, "description": "No such note"}},
    )
    def note(path: str = Query(min_length=1, max_length=512)) -> dict:
        detail = summary.note_detail(vault, path)
        if detail is None:
            return JSONResponse({"detail": "Note not found"}, status_code=404)
        return detail

    @app.get(
        "/api/note/source",
        response_model=models.NoteSource,
        responses={404: {"model": models.ErrorResponse, "description": "No such note"}},
    )
    def note_source(path: str = Query(min_length=1, max_length=512)) -> dict:
        try:
            found = editing.source(vault, path)
        except NoteNotFound:
            return JSONResponse({"detail": "Note not found"}, status_code=404)
        return {**found, "writable": settings.allow_writes}

    # Part (c) of #8: the body only; the frontmatter is kept byte for byte.
    @app.put(
        "/api/note",
        response_model=models.NoteSaved,
        responses={
            403: {"model": models.ErrorResponse, "description": "Writes are turned off"},
            404: {"model": models.ErrorResponse, "description": "No such note"},
            409: {"model": models.SaveConflict, "description": "Changed on disk since opened"},
            413: {"model": models.ErrorResponse, "description": "Too large"},
        },
    )
    def save_note(body: SaveNote) -> dict:
        if not settings.allow_writes:
            return JSONResponse(
                {"detail": "Writes are turned off. Start the server with --allow-writes."},
                status_code=403,
            )
        try:
            saved = editing.save_body(vault, body.path, body.body, body.version)
        except NoteNotFound:
            return JSONResponse({"detail": "Note not found"}, status_code=404)
        except VersionConflict:
            return JSONResponse(
                {
                    "detail": "The note changed on disk since you opened it.",
                    "version": editing.current_version(vault, body.path),
                },
                status_code=409,
            )
        # No cache update needed: search catches up with changed files itself.
        return {"path": saved.path, "version": saved.version}

    @app.get("/api/health", response_model=models.Health)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Last route: everything that isn't /api/* is the frontend.
    mount_frontend(app, settings.frontend_dist or config.DEFAULT_FRONTEND_DIST)

    # Added last = runs first. Outermost: Host check.
    app.add_middleware(ApiGuard, auth=auth, allowed_origins=settings.allowed_origins)
    app.add_middleware(BodySizeLimit, max_bytes=settings.max_body_bytes)
    app.add_middleware(SecurityHeaders)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts), www_redirect=False
    )
    return app
