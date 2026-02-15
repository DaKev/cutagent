---
name: cutagent-merge
description: Merge pull requests to main in the CutAgent open source repository. Use ONLY when the user explicitly asks to merge a PR, land a PR, or ship changes. Triggers on "merge", "merge PR", "land it", "ship it", "merge to main", "close the PR". Do NOT use during normal development — only when the user has finished reviewing and testing.
---

# CutAgent PR Merge Workflow

Only run this when the user explicitly asks to merge. Never merge on your own initiative.

## Pre-Merge Checklist

Before merging, verify all of these:

1. PR is in `OPEN` state and `MERGEABLE`:
   ```bash
   gh pr view <number> --json state,mergeable
   ```
2. CI is passing:
   ```bash
   gh pr checks <number>
   ```
3. PR targets `main`:
   ```bash
   gh pr view <number> --json baseRefName
   ```
4. Review the diff one last time:
   ```bash
   gh pr diff <number>
   ```

If CI is failing or the PR is not mergeable, inform the user and stop.

## Merge Strategy

| PR author | Strategy |
|-----------|----------|
| Owner (DaKev) or AI assistant | **Squash** if multiple small commits; **merge commit** if commits are already clean and meaningful |
| External contributor | Always **squash** for clean history |

```bash
# Squash and merge (combines all commits into one)
gh pr merge <number> --squash --delete-branch

# Merge commit (preserves individual commits)
gh pr merge <number> --merge --delete-branch
```

Use `--admin` flag only when CI is pending on non-code changes (docs, skills).

## Post-Merge Cleanup

After a successful merge, always:

```bash
git checkout main
git pull origin main
git branch -d <branch-name>
```

## Release Tagging

If the merged PR was a release (`release/vX.Y.Z`), tag after merge:

```bash
git checkout main
git pull origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

## Handling External Contributions

When merging an external contributor's PR:

1. Verify code follows CONTRIBUTING.md guidelines
2. Confirm CI passes
3. Confirm JSON output contract is maintained
4. Squash and merge
5. Thank the contributor in the PR comments

## Quick Reference

| Action | Command |
|--------|---------|
| Check PR status | `gh pr view <number> --json state,mergeable` |
| Check CI | `gh pr checks <number>` |
| Review diff | `gh pr diff <number>` |
| Merge (squash) | `gh pr merge <number> --squash --delete-branch` |
| Merge (commit) | `gh pr merge <number> --merge --delete-branch` |
| Sync main | `git checkout main && git pull origin main` |
| Delete branch | `git branch -d feat/thing` |
| Tag release | `git tag -a v0.2.0 -m "Release v0.2.0"` |
