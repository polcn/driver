# CI and Branch Protection

## Workflows

- `CI`: installs backend dependencies, compiles Python sources, runs `ruff`, runs `pytest`, and audits dependencies with `pip-audit`
- `CodeQL`: GitHub code scanning for Python (runs only for public repositories in this repo setup)

## Required branch protection

Protect `main` with these required status checks:

- `backend`

If repository plan/visibility supports CodeQL scanning, also require:

- `analyze (python)`

Recommended additional settings:

- Require a pull request before merging
- Require 1 approval
- Dismiss stale approvals when new commits are pushed
- Require conversation resolution before merging
- Require branches to be up to date before merging

## GitHub API note

Updating branch protection requires repository admin permission and a plan that supports branch protection for the repository visibility. The latest API response for `polcn/driver` returned:

- `403 Upgrade to GitHub Pro or make this repository public to enable this feature.`

That means the remaining blocker is repository plan/visibility, not token scope.
