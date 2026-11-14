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
uv run python -m onyx.try_writes --today 2031-04-16 --identity sheikh
```

It copies `dev-vault/` into a new temporary folder, prints where, and starts the server on the copy with `--allow-writes`. Each run starts from a fresh copy.

In a note, **Edit** opens its body as plain Markdown. **Save** (or ⌘S / Ctrl+S) writes it:

- A toolbar above the text adds Markdown: Heading, Bold, Italic, bulleted and numbered lists, Checkbox, Quote, Link, `[[Wikilink]]` and Code. Each one formats the selected text, or the lines it touches. Pressing it again removes the formatting. ⌘B / Ctrl+B and ⌘I / Ctrl+I work too.
- A live preview beside the text shows the note as Read will (below the text when the window is narrow). A `[[link]]` you've just added is checked against the vault when you save.
- **Changes**, next to Preview, shows your edit line by line: removed lines with −, added lines with +, and two unchanged lines around each change, with the rest folded. It compares against the note as you opened it and keeps no history. Windows line endings don't count as a change. A very large rewrite (more than about 4 million line pairs to compare) isn't compared line by line.

- Only the body is edited. The frontmatter (the fields between the `---` lines, including tags) is shown above the box, and kept byte for byte. Edit fields in Obsidian for now.
- The body includes sections the reading view leaves out, such as `## Status History`.
- If the file changed on disk since you opened it (in Obsidian, say), nothing is saved. Your text stays on screen, with **Reload (discard my edit)** and **Copy my text**.
- Opening and saving without an edit leaves the file byte-for-byte the same, including Windows line endings and a byte-order mark.

### Creating, renaming and deleting notes

These also need `--allow-writes`, and work on notes only: tasks have their own (see Tasks below).

- **New note** on the Notes page makes an empty note in the folder you're viewing (the top level from All notes, a tag or a search) and opens it for editing. `.md` is added to the name. A name can't contain `/ \ : * ? " < > | # ^ [ ]`, and an existing note is never replaced.
- **Rename** (next to Read/Edit on a note) changes the name only; the note stays in its folder. It never replaces another note, and changing only capitals works on the Mac's usual disk. The dialog says how many notes and tasks link to the note: **their `[[links]]` aren't updated**, so they stop working.
- **Delete** moves the note to the vault's `.trash` folder, keeping its folders (`.trash/Projects/Note.md`), like Obsidian's own trash. Get it back from there in Finder or Obsidian. If a note with that name is already in the trash, the new one gets the date and time in its name.
- Rename and delete are refused if the note changed on disk since the dialog opened it. A note reached through a symlink is never moved.

### Tasks

**Tasks** shows every task (a note tagged `task`) as a board by stage (Open, In progress, In review, Done) or as a list. The board is the default. Filter by stage, priority or project; the view and filters stay in the address, so a filtered view can be bookmarked. Opening a task shows it in the focus view. A task whose stage isn't one of the four goes in a **No stage** column, shown only when there is one.

**Cards** show the task's title, the first line of its description, its priority, due date and projects, and its **sub-tasks**. A `projects` link to a note (or to a note not written yet) is a project; a link to another task (a handoff note linking back to its task, say) isn't shown.

**Sub-tasks are the task's own checklist lines** (`- [ ] …`, ticked `- [x] …`), as in Obsidian. They're shown inside the task's card (the first 5, with "+N more") and on the task's page, each with a tick box. A checklist line counts anywhere in the task except inside a code block and under `## Status History` or `## Context`.

**The description** is the text at the top of the task, before its first `## ` heading, without a `# Title` line and without the checklist lines.

**Moving a task** (needs `--allow-writes`): **Move to …** on a card, in the list's Next column or on the task itself moves it one stage on: Open → In progress → In review → Done. Only forward, one stage at a time. Each move changes `status` (and `dateModified`, if the task has one) and adds one line to `## Status History`; nothing else in the note changes. If the task changed on disk since it was read, nothing is moved.

**Sign off and close** (in review → done) needs a sign-off name: start the server with `--identity NAME` (for example `--identity sheikh`). It isn't a login; it records who started the server. Closing is refused if the task's history doesn't end with its move into review, or if any of its sub-tasks isn't ticked. A close writes, in the formats the Sheiko Task Lifecycle plugin uses:

- a `## Context` line: `- **<time> — <name>:** Signed off (not closed)`;
- a history line: `- <time> — in-review → done (signed off by <name> at <time>)`;
- `completedDate`, `closedBy` and `timeToCloseMinutes` only where they're blank, never overwriting, and no duration from a date-only `dateCreated`; plus `closureSource: onyx` when it wrote any of them.

Fields are changed line by line in the frontmatter and checked afterwards. A task whose frontmatter has a field written twice, or the changed field written as a list or block, isn't moved: fix it in Obsidian first.

### Creating and changing tasks

All of these need `--allow-writes`, and refuse if the task changed on disk since it was opened.

- **New task** on the Tasks page makes `Tasks/<title>.md`: `tags: [task]`, `status: open`, `dateCreated`, `dateModified`, the priority and due date if given, the description as its top text, and a `## Status History` holding `created → open`. A name can't contain `/ \ : * ? " < > | # ^ [ ]`, and an existing note is never replaced. A description can't contain a `#` or `##` heading (it would end the description); use `###` or below.
- **Sub-tasks:** on the task's page, **Add a sub-task** adds one `- [ ]` line after the last one (or at the end of the description). Ticking a box changes that one character in the file. A done task's sub-tasks can't change.
- **Edit details** on the task's page changes priority, due date, projects, tags and description. Only fields whose value changes are written, so a value Onyx doesn't show (an unknown priority, say) is kept unless you set that field. Projects are note names, written as `[[links]]`; tags are without `#`. The title is the file name: change it with **Rename**.
- **Rename** keeps the task in its folder; **Delete** moves it to `.trash`, as for notes. Links to it in other notes aren't updated.

**If you also run Sheiko in Obsidian on the same folder**, it adds its own history lines when it sees a status change, so you'd get duplicates. Keep the two apart for now (the real-vault step waits on this).

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
