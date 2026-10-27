# Onyx Sheiko

A local, security-first web app for working with Markdown notes and tasks in an Obsidian-style vault.

> **Status:** early development. v1 (security baseline + Notes and Tasks) is being built; see [issue #1](https://github.com/Ashura-Sheikh/Onyx-Sheiko-FullStack-App-V1/issues/1).

## What it is

- **Notes:** browse a vault's folders, read, edit, create and search Markdown notes.
- **Tasks:** list and create tasks stored as Markdown with frontmatter, and move them through their stages (open → in-progress → in-review → done) with a recorded history.
- **Local only:** the server binds to `127.0.0.1` and serves one user. Your files never leave your machine.

## Stack

| Part | Choice |
|---|---|
| Backend | Python 3.12, [FastAPI](https://fastapi.tiangolo.com/), managed with [uv](https://docs.astral.sh/uv/) |
| Frontend | React + TypeScript, built with [Vite](https://vite.dev/) |
| Styling | [Tailwind CSS](https://tailwindcss.com/) with [Radix UI](https://www.radix-ui.com/) primitives |
| Data | Markdown files are the source of truth; SQLite is only a rebuildable cache |

## Security

Security comes first. The design and its tests are in [`docs/threat-model.md`](docs/threat-model.md); how to report a problem is in [`SECURITY.md`](SECURITY.md).

## Releases

How releases are made, and the gate each one passes before it's published: [`docs/releasing.md`](docs/releasing.md).

## Repository layout

```
backend/     FastAPI app and its tests
frontend/    React + TypeScript app and its tests
dev-vault/   an entirely made-up vault for development and tests
docs/        threat model and design notes
design/      UI mockups
```

## Development

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/); Node.js 24 and npm.

```bash
# Backend
cd backend
uv sync
uv run pytest

# Frontend
cd frontend
npm ci
npm test
npm run build
```

### Running the app

```bash
# 1. Build the frontend (again after frontend changes)
cd frontend
npm ci
npm run build

# 2. Start the server
cd ../backend
uv run python -m onyx --vault ../dev-vault --today 2031-04-16
```

The server prints the address (`http://127.0.0.1:8731`) and a **one-time launch code**, valid for 10 minutes. Open the address, type the code on the sign-in page, and it becomes a session cookie for 12 hours, or until the server stops. You can also set the vault with `ONYX_VAULT` and the port with `--port`.

- The server only ever listens on `127.0.0.1`; there's no option to change that.
- It refuses to start without a vault folder, so it can't fall back to a default one.
- Use `dev-vault/` (made-up data) for development. Connecting a real vault is a separate, later step.
- `--today` fixes the date Home treats as today. The dev-vault's made-up dates are in April 2031, so without it nothing shows as due. Leave it out for a real vault.
- A search cache is rebuilt from the notes on every start, in your cache folder (`~/Library/Caches/onyx-sheiko` on macOS, `~/.cache/onyx-sheiko` elsewhere, or `ONYX_CACHE_DIR`). It's private to your user, never inside the vault or the repo, and always safe to delete.
- The page is served with a strict Content Security Policy and a fresh nonce on every load (see `docs/threat-model.md`, T6).

**Frontend development with live reload:** keep the server running, then `npm run dev` in `frontend/` and open the address Vite prints. Vite forwards `/api` to the server. The CSP applies to the built app served by the server, so check security-related changes there too.

**Trying the API directly:** every `/api` request needs the header `X-Onyx-Request: 1`:

```bash
curl -c "$TMPDIR/onyx-cookies.txt" -H 'X-Onyx-Request: 1' -H 'Content-Type: application/json' \
     -d '{"code": "<launch code>"}' http://127.0.0.1:8731/api/session
curl -b "$TMPDIR/onyx-cookies.txt" -H 'X-Onyx-Request: 1' http://127.0.0.1:8731/api/health
```

## Contributing

Every change goes through a pull request; `main` is protected and CI must pass. Never put real notes, names, paths or secrets in code, tests, issues or pull requests.

## Licence

[MIT](LICENSE)
