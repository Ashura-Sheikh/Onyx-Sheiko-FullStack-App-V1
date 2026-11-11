"""The FastAPI app. Build one with create_app(settings) per server run."""

from datetime import date, datetime
from typing import Literal

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from onyx import config, editing, models, summary, tasks
from onyx.auth import SESSION_COOKIE, AuthState
from onyx.cache import NoteCache, default_cache_dir
from onyx.config import Settings
from onyx.security import ApiGuard, BodySizeLimit, SecurityHeaders, session_from_scope
from onyx.vault import (
    REFUSALS,
    MoveNotSupported,
    NoteExists,
    NoteNotFound,
    PathRejected,
    Vault,
    VersionConflict,
)
from onyx.web import mount_frontend


class LaunchCode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=128)


class SaveNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=512)
    body: str = Field(max_length=config.MAX_BODY_BYTES)
    version: str = Field(pattern=r"^[0-9a-f]{64}$", description="The version the editor opened")


class CreateNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    folder: str = Field(max_length=512, description='An existing folder; "" is the top level')
    name: str = Field(min_length=1, max_length=255, description="The note's name; .md is added")


class RenameNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=512)
    name: str = Field(min_length=1, max_length=255, description="The new name, same folder")
    version: str = Field(pattern=r"^[0-9a-f]{64}$", description="The version that was opened")


class MoveTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=512)
    to: Literal["open", "in-progress", "in-review", "done"]
    version: str = Field(pattern=r"^[0-9a-f]{64}$", description="The version that was opened")


class DeleteNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=512)
    version: str = Field(pattern=r"^[0-9a-f]{64}$", description="The version that was opened")


def now() -> datetime:
    """Local time, for the name of a note moved to .trash over an older one."""
    return datetime.now()


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

    def clock() -> datetime:
        """The time task moves are stamped with: now, or with --today, that
        date at the current time of day. Otherwise moves on the made-up
        dev-vault (dated 2031) would sort before its own history lines."""
        current = now()
        return datetime.combine(settings.today, current.timetz()) if settings.today else current

    # Read-only summaries. Each request reads the files again, so Home is never
    # stale; the cache will take this over when the vault gets large.
    @app.get("/api/home", response_model=models.HomeData)
    def home() -> dict:
        return summary.home(summary.read_summary(vault), today())

    @app.get("/api/items", response_model=models.ItemList)
    def items() -> dict:
        return {"items": summary.items(summary.read_summary(vault))}

    @app.get("/api/tasks", response_model=models.TaskBoard)
    def task_list() -> dict:
        return {"tasks": summary.task_board(summary.read_summary(vault))}

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

    # Part (d) of #8: create, rename, delete. Notes only; tasks are #9.
    def writes_off() -> JSONResponse:
        # A new response each time: middleware adds headers to a response's own list.
        return JSONResponse(
            {"detail": "Writes are turned off. Start the server with --allow-writes."},
            status_code=403,
        )

    def refused(error: Exception) -> JSONResponse:
        if isinstance(error, NoteNotFound):
            return JSONResponse({"detail": "Note not found"}, status_code=404)
        if isinstance(error, editing.TaskNotHere):
            return JSONResponse(
                {"detail": "This is a task. Rename or delete it in Tasks."}, status_code=400
            )
        if isinstance(error, PathRejected):
            # A fixed sentence chosen by code, never the exception's own text.
            detail = REFUSALS.get(error.code, "That name or path isn't allowed.")
            return JSONResponse({"detail": detail}, status_code=400)
        if isinstance(error, VersionConflict):
            return JSONResponse(
                {"detail": "The note changed on disk since you opened it.", "reason": "changed"},
                status_code=409,
            )
        if isinstance(error, NoteExists):
            return JSONResponse(
                {"detail": "A note with that name is already there.", "reason": "exists"},
                status_code=409,
            )
        if isinstance(error, MoveNotSupported):
            return JSONResponse(
                {"detail": "This disk can't move the note safely, so nothing was moved."},
                status_code=500,
            )
        raise error

    write_errors = (
        NoteNotFound,
        editing.TaskNotHere,
        PathRejected,
        VersionConflict,
        NoteExists,
        MoveNotSupported,
    )

    @app.post(
        "/api/notes",
        status_code=201,
        response_model=models.NoteCreated,
        responses={
            400: {"model": models.ErrorResponse, "description": "Name or folder not allowed"},
            403: {"model": models.ErrorResponse, "description": "Writes are turned off"},
            409: {"model": models.MoveRefused, "description": "A note with that name exists"},
        },
    )
    def create_note(body: CreateNote) -> dict:
        if not settings.allow_writes:
            return writes_off()
        try:
            created = editing.create_note(vault, body.folder, body.name)
        except write_errors as error:
            return refused(error)
        return {"path": created.path, "version": created.version}

    @app.post(
        "/api/note/rename",
        response_model=models.NoteRenamed,
        responses={
            400: {"model": models.ErrorResponse, "description": "Name not allowed, or a task"},
            403: {"model": models.ErrorResponse, "description": "Writes are turned off"},
            404: {"model": models.ErrorResponse, "description": "No such note"},
            409: {"model": models.MoveRefused, "description": "Changed on disk, or name taken"},
        },
    )
    def rename_note(body: RenameNote) -> dict:
        if not settings.allow_writes:
            return writes_off()
        try:
            return {"path": editing.rename_note(vault, body.path, body.name, body.version)}
        except write_errors as error:
            return refused(error)

    @app.post(
        "/api/note/delete",
        response_model=models.NoteTrashed,
        responses={
            400: {"model": models.ErrorResponse, "description": "A task"},
            403: {"model": models.ErrorResponse, "description": "Writes are turned off"},
            404: {"model": models.ErrorResponse, "description": "No such note"},
            409: {"model": models.MoveRefused, "description": "Changed on disk since opened"},
        },
    )
    def delete_note(body: DeleteNote) -> dict:
        if not settings.allow_writes:
            return writes_off()
        try:
            return {"trashed_to": editing.delete_note(vault, body.path, body.version, now())}
        except write_errors as error:
            return refused(error)

    @app.get("/api/app-settings", response_model=models.AppSettings)
    def app_settings() -> dict:
        return {"writable": settings.allow_writes, "identity": settings.identity}

    # Part (b) of #9: one stage on; done needs a sign-off (onyx/tasks.py).
    @app.post(
        "/api/task/move",
        response_model=models.TaskMoved,
        responses={
            400: {"model": models.ErrorResponse, "description": "Move refused"},
            403: {"model": models.ErrorResponse, "description": "Writes are turned off"},
            404: {"model": models.ErrorResponse, "description": "No such task"},
            409: {"model": models.MoveRefused, "description": "Changed on disk since opened"},
        },
    )
    def move_task(body: MoveTask) -> dict:
        if not settings.allow_writes:
            return writes_off()
        try:
            moved = tasks.move(vault, body.path, body.to, body.version, settings.identity, clock())
        except tasks.MoveRefused as error:
            detail = tasks.MOVE_REFUSALS.get(error.code, "That move isn't allowed.")
            return JSONResponse({"detail": detail}, status_code=400)
        except (NoteNotFound, VersionConflict) as error:
            return refused(error)
        return {"path": moved.path, "version": moved.version, "status": body.to}

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
