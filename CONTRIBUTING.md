# Contributing

## Current scope

This repository is currently backend-first. Do not assume the PRD is fully implemented. Keep README, CI, and checked-in code aligned with the actual repository contents.

## Before opening a PR

Run the current backend checks:

```bash
make check
```

If dependencies are installed in a clean environment, also run:

```bash
make audit
```

If your change touches the frontend scaffold, make sure `make frontend-smoke` still passes.

## Change expectations

- Prefer small, reviewable PRs
- Update docs when behavior, repo structure, or workflows change
- Add or update tests for backend behavior changes
- Do not advertise features in the README that are not present in the repo
- Keep `docker-compose.yml` runnable from a clean checkout

## Manual merge policy

Branch protection is enforced on `main`. Merges should wait for:

- Required status checks to pass (`backend`, `frontend`, `analyze (python)`)
- Any additional enabled checks to pass (for example `dependency-review`, `actionlint`)
- Any required review/conversation rules to be satisfied in GitHub branch protection

Dependabot patch/minor PRs are eligible for auto-merge after required checks pass.
