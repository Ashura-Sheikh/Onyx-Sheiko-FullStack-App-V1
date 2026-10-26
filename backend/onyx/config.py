"""Settings for one run of the server.

The vault path is required: the app refuses to start without one, so it can
never fall back to some default folder (and never to a real vault by accident).
The server always binds to 127.0.0.1; there is deliberately no option to
change that (threat model: local, single-user).
"""

from dataclasses import dataclass, field
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 8731

# Host header values accepted (DNS-rebinding defence, threat model T3).
ALLOWED_HOSTS = ("127.0.0.1", "localhost")

# Request bodies above this are refused (threat model T7). Notes are text;
# 1 MiB is far above any realistic note.
MAX_BODY_BYTES = 1024 * 1024

# How long the printed launch code stays valid if unused, and how long a
# session lasts. Sessions also end when the server stops (they're in memory).
LAUNCH_CODE_TTL_SECONDS = 10 * 60
SESSION_TTL_SECONDS = 12 * 60 * 60


class ConfigError(ValueError):
    """The settings can't be used; the message says why."""


@dataclass(frozen=True)
class Settings:
    vault: Path
    port: int = DEFAULT_PORT
    launch_code_ttl: int = LAUNCH_CODE_TTL_SECONDS
    session_ttl: int = SESSION_TTL_SECONDS
    max_body_bytes: int = MAX_BODY_BYTES
    allowed_hosts: tuple[str, ...] = field(default=ALLOWED_HOSTS)

    @property
    def allowed_origins(self) -> frozenset[str]:
        """Origins a browser may send for this server (CSRF check, T2)."""
        return frozenset(f"http://{host}:{self.port}" for host in self.allowed_hosts)


def load_settings(vault: str | Path | None, port: int = DEFAULT_PORT) -> Settings:
    if vault is None or str(vault).strip() == "":
        raise ConfigError("A vault folder is required (--vault PATH or ONYX_VAULT).")
    path = Path(vault).expanduser()
    if not path.exists():
        raise ConfigError(f"Vault folder not found: {path}")
    if not path.is_dir():
        raise ConfigError(f"Vault path is not a folder: {path}")
    if not 1024 <= port <= 65535:
        raise ConfigError("Port must be between 1024 and 65535.")
    return Settings(vault=path.resolve(), port=port)
