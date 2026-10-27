"""Try editing notes on a throwaway copy of dev-vault/:

    uv run python -m onyx.try_writes --today 2031-04-16

Copies the committed dev-vault/ into a new temporary folder, prints where it
is, and starts the server on the copy with --allow-writes. The committed
folder itself is never written to (the server refuses --allow-writes for any
folder inside the repository). Each run starts from a fresh copy; old copies
stay in the temporary folder until the system clears it, or you delete them.
Other options (--port, --today) are passed on to the server.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from onyx.__main__ import main as run_server
from onyx.config import REPO_ROOT

DEV_VAULT = REPO_ROOT / "dev-vault"


def make_copy(source: Path = DEV_VAULT) -> Path:
    """A fresh copy of `source` in a new temporary folder, outside the repo."""
    target = Path(tempfile.mkdtemp(prefix="onyx-dev-vault-")) / "dev-vault"
    # symlinks=True: a link is copied as a link, never followed out of the folder.
    shutil.copytree(source, target, symlinks=True)
    return target


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if any(a == "--vault" or a.startswith("--vault=") for a in args):
        print(
            "onyx.try_writes: --vault isn't used here; it always copies dev-vault/.",
            file=sys.stderr,
        )
        return 2
    copy = make_copy()
    print(f"Copied dev-vault/ to {copy}", flush=True)
    return run_server(["--vault", str(copy), "--allow-writes", *args])


if __name__ == "__main__":
    sys.exit(main())
