"""Start the server:  uv run python -m onyx --vault ../dev-vault

Prints the address and a one-time launch code in this terminal. The code is
never logged and never put in a URL; type it into the sign-in page.
"""

import argparse
import os
import sys

import uvicorn

from onyx.app import create_app
from onyx.config import DEFAULT_PORT, HOST, ConfigError, Settings, load_settings


def parse_args(argv: list[str] | None = None) -> Settings:
    parser = argparse.ArgumentParser(prog="python -m onyx", description="Run Onyx Sheiko locally.")
    parser.add_argument("--vault", default=os.environ.get("ONYX_VAULT"), help="vault folder")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    return load_settings(args.vault, args.port)


def uvicorn_config(app, settings: Settings) -> uvicorn.Config:
    # Always 127.0.0.1: there is no option to listen anywhere else.
    return uvicorn.Config(app, host=HOST, port=settings.port, server_header=False)


def main(argv: list[str] | None = None) -> int:
    try:
        settings = parse_args(argv)
    except ConfigError as error:
        print(f"onyx: {error}", file=sys.stderr)
        return 2
    app = create_app(settings)
    print(f"Onyx Sheiko: http://{HOST}:{settings.port}")
    print(f"Vault: {settings.vault}")
    minutes = settings.launch_code_ttl // 60
    print(f"Launch code (one use, {minutes} minutes): {app.state.auth.launch_code}")
    uvicorn.Server(uvicorn_config(app, settings)).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
