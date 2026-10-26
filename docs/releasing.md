# Releasing

How a version of Onyx Sheiko is released, and the gate it must pass first.

## What a release is

A release is:

1. a **version tag** (`v0.1.0`, `v1.0.0`, …) on a commit on `main`, and
2. a **GitHub release** for that tag, with release notes.

Releases are **source only**. No built files or binaries are attached; you build from the tagged source. Nothing reaches `main` except through a pull request with passing checks.

## Version numbers

[Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

- **0.x:** before v1. Anything may change.
- **1.0.0:** v1 is complete (the security baseline plus Notes and Tasks, issue #1).
- After 1.0.0: PATCH for fixes, MINOR for new features that don't break anything, MAJOR for breaking changes.

The version lives in `backend/pyproject.toml` and `frontend/package.json`, and both must match the tag.

## Steps

1. **Version PR.** Bump the version in both files and add the release notes to the PR description. Merge it once the checks pass.
2. **Tag.** Tag the merge commit on `main` with `vX.Y.Z` and push the tag.
3. **Gate.** A reviewer checks every gate item below on a **fresh clone of the tag**, not a working copy, and records the results.
4. **Owner's check.** The owner runs the tagged build locally and checks it in a browser.
5. **Publish.** Only after the gate passes and the owner signs off: create the GitHub release for the tag, with the notes.

If any gate item fails, the release isn't published. Fix it in a new PR and tag a new patch version; a published tag is never moved.

## Gate items

Each item is checked on the tagged commit, with the evidence written down (counts, run links, outputs).

- [ ] **Checks green:** CI, the security workflow and CodeQL all passed on the tagged commit.
- [ ] **Tests on a clean clone:** backend and frontend tests pass on a fresh clone of the tag; counts recorded.
- [ ] **Threat model covered:** every threat in [`threat-model.md`](threat-model.md) that applies to this release has its test, and it passes.
- [ ] **No real data:** the `dev-vault/` checks pass, and the issue, PR and release text for this release contain no real notes, names, paths or secrets.
- [ ] **Dependencies:** `pip-audit` and `npm audit` are clean, or every exception is written down with a reason.
- [ ] **Versions match:** the tag, `backend/pyproject.toml` and `frontend/package.json` show the same version.
- [ ] **Release notes** describe what actually changed since the last release.
- [ ] **Owner's live check:** the owner ran it locally and checked the changed features in a browser.

## Before v1.0.0

Pre-1.0 releases (`0.x`) go through the same gate. The first real-vault use is **not** part of any release: connecting the app to a real vault, read-only first, is a separate step with its own sign-off.
