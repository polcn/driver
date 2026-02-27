# CI and Branch Protection

## Workflows

- `CI`: installs backend dependencies, compiles Python sources, runs `ruff`, runs `pytest`, and audits dependencies with `pip-audit`
- `CodeQL`: GitHub code scanning for Python

## Required branch protection

Protect `main` with these required status checks:

- `backend`
- `frontend`
- `analyze (python)`

Recommended additional settings:

- Require a pull request before merging
- Require 1 approval
- Dismiss stale approvals when new commits are pushed
- Require conversation resolution before merging
- Require branches to be up to date before merging
- Block force pushes
- Do not allow branch deletion
