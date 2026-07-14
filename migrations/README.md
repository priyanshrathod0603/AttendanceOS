# Database migrations

The application performs an idempotent schema upgrade at startup:

```bash
python3 app.py
```

`db.create_all()` creates all additive enterprise tables and
`ensure_schema_compat()` safely adds compatible columns to legacy tables.
No existing table or row is dropped.

For an explicit upgrade without starting the web server:

```bash
python3 scripts/init_db.py
```

When Flask-Migrate is added to a deployment, generate the equivalent
revision with `flask db migrate -m "enterprise attendance"` and apply it
with `flask db upgrade`.
