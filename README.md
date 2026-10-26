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

How to run the app itself will be added with the backend skeleton (issue #4).

## Contributing

Every change goes through a pull request; `main` is protected and CI must pass. Never put real notes, names, paths or secrets in code, tests, issues or pull requests.

## Licence

[MIT](LICENSE)
