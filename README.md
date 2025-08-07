### Database initialisation

For local development you can bootstrap the SQLite database (create tables or run migrations) with:

```bash
make db-init
```

This target simply runs the application’s Alembic migrations up to *head* (or `create_all` when `ENV=dev`).

