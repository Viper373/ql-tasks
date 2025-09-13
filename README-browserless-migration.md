DrissionPage -> Browserless Migration Scaffold

This scaffold helps migrate Python automation from DrissionPage to Browserless using Playwright (Python) over CDP.

### 1) Run Browserless

Using Docker Compose:

```
docker compose up -d
```

- Service listens on `http://localhost:3000`.
- To enable auth, set `BROWSERLESS_TOKEN` in your environment before starting compose.

Example:

```
export BROWSERLESS_TOKEN=your-strong-token
docker compose up -d
```

### 2) Python setup

Install dependencies:

```
pip install -r requirements.txt
```

Playwright does not need local browsers when connecting over CDP to Browserless.

Environment variables (optional):
- `BROWSERLESS_WS_URL`: Full ws(s) URL, e.g. `ws://localhost:3000?token=XYZ`
- `BROWSERLESS_URL`: Base URL, e.g. `http://localhost:3000` (token will be appended)
- `BROWSERLESS_TOKEN`: Token appended if not in URL

### 3) DrissionPage-style adapter

- `src/browserless_client.py`: CDP client wrapper
- `src/adapter/dp_adapter.py`: Minimal DP-like API (`get`, `ele`, `click`, `input`, `text`, `html`, `screenshot`, `pdf`)

### 4) Example

```
PYTHONPATH=src python examples/dp_migration_example.py
```

It navigates to `https://example.com`, prints the H1 text, and saves `examples/shot.png`.

### 5) Notes for migration

- Map selectors: use `css:`, `xpath:`, or `text:` prefixes to disambiguate.
- Replace DP-specific APIs progressively by wrapping them inside the adapter or calling Playwright APIs directly on `page._client.browser`/`context` if needed.
- Tune concurrency via Docker envs: `MAX_CONCURRENT_SESSIONS`, `QUEUE_LENGTH`. Enable `TOKEN` for auth.

### 6) Troubleshooting

- Connection refused: ensure container is up and reachable on port 3000.
- Auth errors: add `?token=...` to `BROWSERLESS_WS_URL` or set `BROWSERLESS_TOKEN`.
- PDF requires Chromium headless mode (default in Browserless) and proper permissions.
