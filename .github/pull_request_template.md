## Summary

- Describe the user-visible or API-visible change
- Call out any schema, CI, or deployment changes

## Validation

- [ ] `python -m compileall backend/app tests`
- [ ] `ruff check backend tests`
- [ ] `ruff format --check backend tests`
- [ ] `PYTHONPATH=backend pytest -q tests`

## Review Focus

- [ ] API behavior changed
- [ ] Schema changed
- [ ] Documentation updated
- [ ] CI/workflow changed

## Risks

- Note regressions, migration concerns, or follow-up work
