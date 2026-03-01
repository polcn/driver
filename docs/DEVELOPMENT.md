# Development

## Local backend workflow

Install dependencies:

```bash
make install-dev
make install-frontend
```

Run the backend locally:

```bash
make run
```

Run the current quality checks:

```bash
make check
```

Build only the frontend:

```bash
make frontend-build
```

Run the frontend smoke check:

```bash
make frontend-smoke
```

Run the dependency audit separately:

```bash
make audit
```

Run the legacy food migration:

```bash
python3 scripts/migrate_health_db.py /path/to/health.db /path/to/driver.db --dry-run
python3 scripts/migrate_health_db.py /path/to/health.db /path/to/driver.db
```

## Notes

- The backend serves both the API and built frontend static files on port 8000
- The SQLite database path is configured via `DATABASE_PATH` environment variable
- Tests use an isolated temporary SQLite database per test run
- Docker files (`docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`) remain in the repo for CI reference
