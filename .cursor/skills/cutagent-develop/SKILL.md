---
name: cutagent-develop
description: Development workflow for the CutAgent open source repository. Use when writing code, committing changes, creating branches, pushing, or opening pull requests. Triggers on "commit", "push", "PR", "pull request", "branch", "implement", "add", "fix", "refactor", or any coding task in this project. Does NOT handle merging — that is a separate skill. Enforces branch protection, conventional commits, and PR-based development.
---

# CutAgent Development Workflow

This project is public open source at https://github.com/DaKev/cutagent. All changes go through pull requests — never push directly to `main`.

**IMPORTANT: This skill covers development up to opening a PR. Do NOT merge — the user will review, test locally, and explicitly ask to merge when ready.**

## Golden Rule

**Never commit or push directly to `main`.** Every change goes through a feature branch and a pull request.

## 1. Create a Feature Branch

Always branch from latest `main`:

```bash
git checkout main
git pull origin main
git checkout -b <type>/<short-description>
```

### Branch Naming

Format: `<type>/<short-kebab-description>`

| Type | Use for |
|------|---------|
| `feat/` | New features or operations |
| `fix/` | Bug fixes |
| `docs/` | Documentation changes |
| `test/` | Adding or updating tests |
| `refactor/` | Code restructuring without behavior change |
| `chore/` | Build, CI, tooling, dependency updates |
| `release/` | Release preparation |

Examples: `feat/speed-operation`, `fix/trim-keyframe-warning`, `docs/edl-examples`

## 2. Make Commits

Use **Conventional Commits** format:

```
<type>: <concise description of why>
```

**Types** (same as branch prefixes): `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`

Rules:
- Subject line: imperative mood, lowercase, no period, max 72 chars
- Focus on **why**, not what (the diff shows what)
- One logical change per commit — don't bundle unrelated changes
- Never commit secrets, `.env` files, or large binary files

Good examples:
```
feat: add speed change operation for playback rate control
fix: handle empty keyframe list in trim warnings
docs: add crossfade examples to EDL format section
```

Bad examples:
```
updated stuff           # vague
Fix bug.                # period, no context
feat: Add new feature   # capitalized, redundant
WIP                     # don't commit work-in-progress
```

## 3. Pre-Commit Checks

Before committing, always:

1. Run `pytest` — all tests must pass
2. Verify no non-JSON output leaks to stdout in CLI commands
3. Check for any unintended file changes with `git diff`
4. Ensure no secrets or `.env` files are staged

## 4. Push and Open a Pull Request

```bash
git push -u origin HEAD
```

Then create a PR using `gh pr create`. The PR must follow the template in `.github/PULL_REQUEST_TEMPLATE.md`.

PR title format matches commit convention: `<type>: <description>`

PR body must include:
- **What**: Brief description of changes
- **Why**: Problem solved or motivation
- **How**: Approach and notable implementation details
- **Checklist**: All items from the PR template

## 5. STOP — Wait for User

After opening the PR, **stop and inform the user**. Do not merge. The user will:
- Review the changes
- Test locally
- Request further changes
- Explicitly ask to merge when satisfied

## Release Preparation

When preparing a release:

1. Create branch: `release/vX.Y.Z`
2. Update version in `cutagent/__init__.py` and `pyproject.toml`
3. Update `CHANGELOG.md` with all changes since last release
4. Open PR titled `release: vX.Y.Z`
5. Stop — tagging happens after merge (handled by the merge skill)

## Quick Reference

| Action | Command |
|--------|---------|
| New branch | `git checkout -b feat/thing` |
| Stage all | `git add -A` |
| Commit | `git commit -m "feat: description"` |
| Push branch | `git push -u origin HEAD` |
| Create PR | `gh pr create --title "feat: thing" --body "..."` |
| Sync main | `git checkout main && git pull origin main` |
