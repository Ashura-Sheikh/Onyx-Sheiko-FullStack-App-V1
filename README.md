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

### Editing notes

Notes can be edited only when the server is started with `--allow-writes`. Without it, the editor opens read-only and every save is refused. `--allow-writes` is refused for any folder inside this repository, so the committed `dev-vault/` is never changed. To try editing, run the server on a fresh copy of `dev-vault/` instead:

```bash
cd backend
uv run python -m onyx.try_writes --today 2031-04-16
```

It copies `dev-vault/` into a new temporary folder, prints where, and starts the server on the copy with `--allow-writes`. Each run starts from a fresh copy.

In a note, **Edit** opens its body as plain Markdown. **Save** (or ⌘S / Ctrl+S) writes it:

- A toolbar above the text adds Markdown: Heading, Bold, Italic, bulleted and numbered lists, Checkbox, Quote, Link, `[[Wikilink]]` and Code. Each one formats the selected text, or the lines it touches. Pressing it again removes the formatting. ⌘B / Ctrl+B and ⌘I / Ctrl+I work too.
- A live preview beside the text shows the note as Read will (below the text when the window is narrow). A `[[link]]` you've just added is checked against the vault when you save.

- Only the body is edited. The frontmatter (the fields between the `---` lines, including tags) is shown above the box, and kept byte for byte. Edit fields in Obsidian for now.
- The body includes sections the reading view leaves out, such as `## Status History`.
- If the file changed on disk since you opened it (in Obsidian, say), nothing is saved. Your text stays on screen, with **Reload (discard my edit)** and **Copy my text**.
- Opening and saving without an edit leaves the file byte-for-byte the same, including Windows line endings and a byte-order mark.

Rename and delete come in a later part of [#8](https://github.com/Ashura-Sheikh/Onyx-Sheiko-FullStack-App-V1/issues/8).

**Frontend development with live reload:** keep the server running, then `npm run dev` in `frontend/` and open the address Vite prints. Vite forwards `/api` to the server. The CSP applies to the built app served by the server, so check security-related changes there too.

**Trying the API directly:** every `/api` request needs the header `X-Onyx-Request: 1`:

```bash
curl -c "$TMPDIR/onyx-cookies.txt" -H 'X-Onyx-Request: 1' -H 'Content-Type: application/json' \
     -d '{"code": "<launch code>"}' http://127.0.0.1:8731/api/session
curl -b "$TMPDIR/onyx-cookies.txt" -H 'X-Onyx-Request: 1' http://127.0.0.1:8731/api/health
```

### Changing the API

The frontend's API types are generated from the backend, so the two can't drift apart:

1. Change the response models in `backend/onyx/models.py` (and the endpoint in `backend/onyx/app.py`).
2. Write the schema: `uv run python -m onyx.schema` in `backend/` (updates `frontend/openapi.json`).
3. Generate the types: `npm run gen:api` in `frontend/` (updates `frontend/src/api-types.ts`).
4. Commit all three. A backend test fails if `openapi.json` is out of date, and a frontend test fails if `api-types.ts` is.

`apiGet('/api/…')` in `frontend/src/api.ts` is typed from that file: the path decides the response type, and an endpoint that doesn't exist won't type-check. The server itself never serves its schema.

## Contributing

Every change goes through a pull request; `main` is protected and CI must pass. Never put real notes, names, paths or secrets in code, tests, issues or pull requests.

## Licence

[MIT](LICENSE)
