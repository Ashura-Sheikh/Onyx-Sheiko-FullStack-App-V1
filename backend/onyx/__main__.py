"""Start the server:  uv run python -m onyx --vault ../dev-vault --today 2031-04-16

Prints the address and a one-time launch code in this terminal. The code is
never logged and never put in a URL; type it into the sign-in page.
"""

import argparse
import os
import sys

import uvicorn

from onyx.app import create_app
from onyx.cache import CacheLocationError
from onyx.config import DEFAULT_PORT, HOST, ConfigError, Settings, load_settings


def parse_args(argv: list[str] | None = None) -> Settings:
    parser = argparse.ArgumentParser(prog="python -m onyx", description="Run Onyx Sheiko locally.")
    parser.add_argument("--vault", default=os.environ.get("ONYX_VAULT"), help="vault folder")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--today", help="treat this date (YYYY-MM-DD) as today; for the made-up dev-vault"
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        help="let the app change notes (off by default; refused for folders inside the repo)",
    )
    args = parser.parse_args(argv)
    return load_settings(args.vault, args.port, args.today, args.allow_writes)


def uvicorn_config(app, settings: Settings) -> uvicorn.Config:
    # Always 127.0.0.1: there is no option to listen anywhere else.
    return uvicorn.Config(app, host=HOST, port=settings.port, server_header=False)


def main(argv: list[str] | None = None) -> int:
    try:
        settings = parse_args(argv)
    except ConfigError as error:
        print(f"onyx: {error}", file=sys.stderr)
        return 2
    try:
        app = create_app(settings)
    except CacheLocationError as error:
        print(f"onyx: {error}", file=sys.stderr)
        return 2
    minutes = settings.launch_code_ttl // 60
    # flush=True: when output isn't a terminal (an IDE task, a pipe), Python
    # buffers it, and the code wouldn't appear until the server stopped.
    print(f"Onyx Sheiko: http://{HOST}:{settings.port}", flush=True)
    print(f"Vault: {settings.vault}", flush=True)
    print(f"Cache: {app.state.cache.path}", flush=True)
    print(f"Writes: {'on (--allow-writes)' if settings.allow_writes else 'off'}", flush=True)
    if settings.today is not None:
        print(f"Today (fixed with --today): {settings.today.isoformat()}", flush=True)
    print(f"Launch code (one use, {minutes} minutes): {app.state.auth.launch_code}", flush=True)
    uvicorn.Server(uvicorn_config(app, settings)).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
