# Security policy

Security is the first priority of this project. Thank you for helping keep it safe.

## Reporting a vulnerability

Please **don't** open a public issue for a security problem.

Report it privately through GitHub: on this repository's **Security** tab, choose **Report a vulnerability**. Include what you found, how to reproduce it, and what an attacker could do with it.

You'll get a reply as soon as possible. Once a fix is released, the report can be made public, with credit if you'd like it.

## Supported versions

Onyx Sheiko is in early development (v1 not yet released). Only the latest code on `main` is supported.

## How the app is designed to be safe

The full threat model is in [`docs/threat-model.md`](docs/threat-model.md). In short:

- It runs **locally**, bound to `127.0.0.1`, for a single user.
- Login uses a **one-time launch code** that becomes an HttpOnly, SameSite=Strict cookie. No token ever appears in a URL.
- Every API request needs the session cookie **and** a custom header, and the `Host` and `Origin` headers are checked.
- All file access goes through **one path guard** that keeps it inside the configured vault.
- A strict **Content Security Policy** blocks inline scripts and styles.
- v1 makes **no AI model or other outbound calls** with your notes.
- The repository contains **no real data**: the test vault in `dev-vault/` is entirely made up.
