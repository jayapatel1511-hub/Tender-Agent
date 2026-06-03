# Repo Refresh

Purpose: verify the repo is safe to use before running tender monitoring.

## Steps

1. Work in `C:\Users\jpate\Tender-Agent`.
2. Run:

```powershell
git status --short --branch
git remote -v
```

3. If a remote exists, run:

```powershell
git fetch --all --prune
```

4. Compare local `HEAD` to upstream. Pull only if the worktree is clean and the branch can fast-forward safely:

```powershell
git rev-parse --abbrev-ref --symbolic-full-name '@{u}'
git merge-base --is-ancestor HEAD '@{u}'
git pull --ff-only
```

5. If there are uncommitted or untracked files, do not pull. Report the state and continue only if the requested monitor run can proceed without disturbing local work.

## Output

Report branch, remote, dirty/clean state, pull result, and any reason the pull was skipped.
