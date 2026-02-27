# Development

## Local backend workflow

Install dependencies:

```bash
make install-dev
```

Run the backend locally:

```bash
make run
```

Run the current quality checks:

```bash
make check
```

Run the dependency audit separately:

```bash
make audit
```

## Notes

- The current repository is backend-only in practice; `docker-compose.yml` starts only the API service
- The SQLite database defaults to `/data/driver.db` in Docker and can be overridden with `DATABASE_PATH`
- Tests use an isolated temporary SQLite database per test run
