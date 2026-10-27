"""Write the API's OpenAPI schema to frontend/openapi.json.

    uv run python -m onyx.schema

The running server never serves its schema (openapi_url=None in app.py); it's
generated here instead, from the response models in onyx/models.py, and
committed. The frontend generates its types from the committed file
(npm run gen:api). Tests fail if either is out of date.
"""

import json
import sys
import tempfile
from pathlib import Path

from onyx.config import REPO_ROOT, Settings

SCHEMA_FILE = REPO_ROOT / "frontend" / "openapi.json"
DEV_VAULT = REPO_ROOT / "dev-vault"


def openapi_schema() -> dict:
    # The schema doesn't depend on the vault; the made-up dev-vault and a
    # throwaway cache folder are only there because the app needs both to start.
    from onyx.app import create_app

    with tempfile.TemporaryDirectory() as cache:
        return create_app(Settings(vault=DEV_VAULT, cache_dir=Path(cache))).openapi()


def schema_text() -> str:
    return json.dumps(openapi_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    SCHEMA_FILE.write_text(schema_text(), encoding="utf-8")
    print(f"Wrote {SCHEMA_FILE.relative_to(REPO_ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
