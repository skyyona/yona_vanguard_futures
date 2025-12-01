This directory contains locally generated patch artifacts and a git bundle for offline review and application.

Files created
- `.git_patches/` : directory with patch files (.patch) created by `git format-patch` for recent commits.
- `.git_patches/changes.bundle` : git bundle containing branches `fix/strategy-layout-safety-apply` and `fix/step1-only` (fallback to full bundle if needed).

Recommended ways to review / apply locally

1) Apply individual patch files (reviewable, safe)
- Inspect patches:
  - `ls .git_patches` or open files in editor.
- Apply via `git am` (preserves authorship & metadata):

```powershell
# from repo root
git checkout -b review/layout-safety-apply
git am .git_patches/*.patch
```

- If `git am` fails (conflicts), abort with `git am --abort`, inspect and apply manually via `git apply` or edit patch.

2) Use the git bundle (complete branch transfer)
- To fetch and check out the bundled branches locally (recommended if you want the exact branch commits):

```powershell
# create a temp clone or use existing repo
mkdir tmp_repo_clone; cd tmp_repo_clone
git init
# fetch bundle into the new repo
git bundle unbundle ../.git_patches/changes.bundle
# list refs contained
git bundle verify ../.git_patches/changes.bundle || true
# alternatively, fetch into an existing repo:
# from repo root
git fetch ../.git_patches/changes.bundle refs/heads/*:refs/remotes/bundle/*
# then inspect
git branch -r
# create a local branch from the fetched remote
git checkout -b fix/strategy-layout-safety-apply refs/remotes/bundle/fix/strategy-layout-safety-apply
```

3) Manual diff apply (if you prefer):

```powershell
# create unified diff of current branch vs main
git diff main..fix/strategy-layout-safety-apply > .git_patches/layout-safety.diff
# apply (dry-run first)
git apply --check .git_patches/layout-safety.diff
git apply .git_patches/layout-safety.diff
```

Notes & guidance
- The patches include: logging and error-surfacing, defensive type coercions for `executable_parameters`, and an atomic content-widget swap to avoid QLayout warnings.
- I recommend applying the patches to a dedicated review branch, running the included diagnostic scripts, and performing the interactive GUI test before merging.
- If you want, I can prepare a PR description and checklist file for reviewers (but you mentioned no remote). I can also create an archive (zip) of `.git_patches/` for transfer.

If you want me to also:
- create a ZIP of `.git_patches/` in the workspace,
- prepare a ready-to-paste PR body and release notes,
- or run further local tests on these branches,
say which and I'll proceed.
