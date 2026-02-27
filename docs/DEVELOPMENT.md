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

Build only the frontend scaffold:

```bash
make frontend-build
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

- `docker-compose.yml` starts both the API service and the minimal frontend scaffold
- The SQLite database defaults to `/data/driver.db` in Docker and can be overridden with `DATABASE_PATH`
- Tests use an isolated temporary SQLite database per test run
