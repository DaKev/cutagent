---
name: cutagent-git-workflow
description: Professional open source git workflow for the CutAgent repository. Use when committing code, creating branches, opening pull requests, tagging releases, or any git operation in this project. Triggers on "commit", "push", "PR", "pull request", "merge", "release", "branch", "tag", or any git-related task. Enforces branch protection, conventional commits, and PR-based workflow.
---

# CutAgent Git Workflow

This project is public open source at https://github.com/DaKev/cutagent. All changes go through pull requests — never push directly to `main`.

## Golden Rule

**Never commit or push directly to `main`.** Every change — no matter how small — goes through a feature branch and a pull request.

## Branch Workflow

### 1. Create a Feature Branch

Always branch from latest `main`:

```bash
git checkout main
git pull origin main
git checkout -b <type>/<short-description>
```

### Branch Naming Convention

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

Examples: `feat/speed-operation`, `fix/trim-keyframe-warning`, `docs/edl-examples`, `chore/ci-python-3.14`

### 2. Make Commits

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
test: cover split with out-of-range points
refactor: extract keyframe alignment check into shared helper
chore: add Python 3.14 to CI matrix
```

Bad examples:
```
updated stuff           # vague
Fix bug.                # period, no context
feat: Add new feature   # capitalized, redundant
WIP                     # don't commit work-in-progress
```

### 3. Push and Open a Pull Request

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

### 4. Merge a Pull Request

When asked to merge a PR, follow this checklist:

**Pre-merge checks:**

1. Verify PR is in `OPEN` state and `MERGEABLE`
2. Review the diff: `gh pr diff <number>`
3. Check CI status: `gh pr checks <number>`
4. Confirm the PR targets `main`

**Merge strategy:**

| PR author | Strategy | Command |
|-----------|----------|---------|
| Owner (DaKev) or AI assistant | **Squash and merge** if multiple small commits; **merge commit** if commits are already clean | See below |
| External contributor | Always **squash and merge** for clean history | See below |

```bash
# Squash and merge (combines all commits into one)
gh pr merge <number> --squash --delete-branch

# Merge commit (preserves individual commits)
gh pr merge <number> --merge --delete-branch
```

The `--delete-branch` flag removes the remote feature branch after merge.

**Post-merge cleanup:**

```bash
git checkout main
git pull origin main
git branch -d <branch-name>
```

Always sync local `main` and delete the local branch after merging.

## Pre-Commit Checks

Before committing, always:

1. Run `pytest` — all tests must pass
2. Verify no non-JSON output leaks to stdout in CLI commands
3. Check for any unintended file changes with `git diff`
4. Ensure no secrets or `.env` files are staged

## Release Workflow

When preparing a release:

1. Create branch: `release/vX.Y.Z`
2. Update version in `cutagent/__init__.py` and `pyproject.toml`
3. Update `CHANGELOG.md` with all changes since last release
4. Open PR titled `release: vX.Y.Z`
5. After merge, tag on main:

```bash
git checkout main
git pull origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

## Handling External Contributions

When someone opens a PR against this repo:

1. Review the code against CONTRIBUTING.md guidelines
2. Check that tests pass in CI
3. Ensure JSON output contract is maintained
4. Merge using **squash and merge** for clean history
5. Thank the contributor

## Quick Reference

| Action | Command |
|--------|---------|
| New branch | `git checkout -b feat/thing` |
| Stage all | `git add -A` |
| Commit | `git commit -m "feat: description"` |
| Push branch | `git push -u origin HEAD` |
| Create PR | `gh pr create --title "feat: thing" --body "..."` |
| Review PR | `gh pr diff <number>` |
| Check CI | `gh pr checks <number>` |
| Merge (squash) | `gh pr merge <number> --squash --delete-branch` |
| Merge (commit) | `gh pr merge <number> --merge --delete-branch` |
| Sync main | `git checkout main && git pull origin main` |
| Delete branch | `git branch -d feat/thing` |
| Tag release | `git tag -a v0.2.0 -m "Release v0.2.0"` |
