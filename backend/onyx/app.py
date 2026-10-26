"""The FastAPI app. Build one with create_app(settings) per server run."""

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from onyx.auth import SESSION_COOKIE, AuthState
from onyx.cache import NoteCache, default_cache_dir
from onyx.config import Settings
from onyx.security import ApiGuard, BodySizeLimit, SecurityHeaders, session_from_scope
from onyx.vault import Vault


class LaunchCode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=128)


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

    @app.post("/api/session", status_code=204)
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

    @app.get("/api/session")
    def session_status(request: Request) -> dict[str, bool]:
        return {"authenticated": auth.is_valid_session(session_from_scope(request.scope))}

    @app.delete("/api/session", status_code=204)
    def sign_out(request: Request) -> Response:
        auth.end_session(session_from_scope(request.scope))
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Added last = runs first. Outermost: Host check.
    app.add_middleware(ApiGuard, auth=auth, allowed_origins=settings.allowed_origins)
    app.add_middleware(BodySizeLimit, max_bytes=settings.max_body_bytes)
    app.add_middleware(SecurityHeaders)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts), www_redirect=False
    )
    return app
