# Threat model (v1)

One page: what we protect, how it could be attacked, and how each threat is stopped and tested. Every row in the threats table needs a passing test before v1 is released.

## Scope

v1 is a **local, single-user** web app: a FastAPI server bound to `127.0.0.1`, serving a React frontend, reading and writing Markdown files in one configured vault folder. v1 makes no AI model calls and no outbound network requests with note content.

## Assets

| Asset | Why it matters |
|---|---|
| The vault's Markdown files | The user's notes and tasks; confidentiality and integrity |
| Files outside the vault | Must never be readable or writable through the app |
| The session (launch code, cookie) | Whoever holds it can read and write the vault |
| The SQLite cache | Holds copies of note content |
| This public repository | Must never contain real notes, paths, names or secrets |

## Entry points

- HTTP requests to `127.0.0.1:<port>` (the API and the static frontend)
- Note content rendered in the browser
- The terminal where the server prints the launch code
- Pull requests, dependencies and CI workflows (supply chain)

## Threats, mitigations and tests

| # | Threat | Mitigation | Test |
|---|---|---|---|
| T1 | Another local process or a web page calls the API | Session cookie (from the one-time launch code) required on every `/api/*` request | 401 without the cookie |
| T2 | Cross-site request forgery from a page in the same browser | SameSite=Strict cookie, plus a required custom header, plus an `Origin` check on state-changing requests | 403 without the header; 403 with a foreign `Origin` |
| T3 | DNS rebinding (a site resolving its name to `127.0.0.1`) | `Host` header allowlist: `127.0.0.1` and `localhost` only | 400/403 for any other `Host` |
| T4 | Token leaks through URLs (history, logs, screenshots, `Referer`) | No token or code in any URL; the launch code is single-use and short-lived; `Referrer-Policy: no-referrer` | Launch code can't be reused; no `token` query parameter accepted |
| T5 | Path traversal to read or write outside the vault | One path guard for every file access: resolve the real path, require it inside the vault, refuse dotfiles, `.git` and symlinks that leave the vault | `..`, encoded `..`, absolute paths and an escaping symlink are rejected |
| T6 | Stored XSS: note content runs as script | React escapes text by default; Markdown is rendered by `react-markdown` into React elements, never an HTML string, with raw HTML in a note dropped (`skipHtml`), links limited to safe protocols (its default `urlTransform`: no `javascript:`; the only addition is the app's own `onyx-note:` address for `[[wikilinks]]`, which never reaches the browser as a link: it's turned into an in-app link to the note the server resolved, or plain text), and images not loaded; no `dangerouslySetInnerHTML` (lint rule); strict CSP: `default-src 'self'`, `script-src 'self'` (no inline script, ever), `style-src 'self'` on API responses and `style-src 'self' 'nonce-…'` on the HTML page only, with a fresh 128-bit nonce per page load, so only the `<style>` tags Radix creates (tagged with that nonce) are allowed. Never `unsafe-inline` | An XSS payload in a note title and body renders as text; in the focus view, raw HTML, `<script>`, a `javascript:` link and an image create no element and no unsafe link; CSP header present; each page load gets a new nonce in its CSP and meta tag; API CSP has no nonce; no `unsafe` anywhere |
| T7 | Oversized or malformed requests | Pydantic models with size limits on every body; a request size cap | Oversized body rejected; invalid body gives 422 |
| T8 | Lost or corrupted notes from a bad write | Atomic writes (temp file, then rename); refuse to write if the file changed on disk since it was read. Writes only when the server is started with `--allow-writes`, which is refused for any folder inside the repo (`python -m onyx.try_writes` copies `dev-vault/` to a temporary folder). Editing replaces the body only: the frontmatter is kept as raw text, never rebuilt from parsed fields (which would drop what the parser can't read). A note saved with `\r\n` line endings throughout gets them back, since a browser text box gives `\n` | Concurrent-change write is refused and the file is unchanged; a second save from the same version is refused; malformed, oversized or unknown frontmatter is kept exactly; saving without an edit gives the same SHA-256 for `\r\n`, byte-order-mark and no-final-newline files; a save is 403 without `--allow-writes`; `--allow-writes` on `dev-vault/` is refused; a save through `..`, a hidden folder, an unlisted name or an escaping symlink is 404 and changes nothing |
| T9 | Secrets or note content in logs | Logging rule: no note content, launch code or cookie values in logs | Log output checked for the launch code and a known note string |
| T10 | Cache leaks note content, or search is abused | SQLite cache in a per-user cache folder outside the vault and the repo, folder 0700 and file 0600 (it holds note text for search); `.gitignore` covers database files; rebuildable from the files. Search text is reduced to plain words before it reaches FTS5 (no operators, at most 10 words, 200 characters), results are capped at 20, and snippets come back as plain text parts, never HTML | Cache path is outside the vault and repo; cache rebuilds from files and stays 0600 after searching; typed quotes and operators can't change a query; a hostile snippet renders as text |
| T11 | Real data committed to the public repo | `dev-vault/` is entirely made up and every file is marked `synthetic: true`; issue, PR and release text written fresh | A test rejects unmarked files, absolute paths, email addresses and non-`example.com` URLs in `dev-vault/` |
| T12 | Secrets committed to the repo | GitHub secret scanning with push protection; gitleaks in CI | gitleaks job passes on every PR |
| T13 | Vulnerable or malicious dependencies | Lockfiles committed; Dependabot; `pip-audit` and `npm audit` in CI; CodeQL; Bandit | Audit jobs pass on every PR |
| T14 | Compromised CI action | Every action pinned to a full commit SHA; workflow tokens read-only | Reviewed in each workflow PR |
| T15 | A note's frontmatter attacks the parser (code execution, huge or deeply nested YAML) | `yaml.safe_load` only (no Python objects); frontmatter over 64 KiB ignored; every value checked and unknown ones dropped before it reaches the API; titles capped at 300 characters | Tests: a `!!python/object` tag gives no fields; oversized and deeply nested frontmatter give no fields, and one such note doesn't break Home; unknown status and priority dropped |

## Out of scope for v1

- Use by more than one person, or from another device. Going beyond `127.0.0.1` needs its own security review first (accounts, HTTPS, per-user permissions).
- Running scripts or calling AI models. Each gets its own security review before it's built.
- A malicious user with full access to the same computer account. They can already read the vault files directly.
