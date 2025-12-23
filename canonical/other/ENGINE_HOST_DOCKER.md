Engine Host — Docker quickstart

Build image (from repo root):

```powershell
docker build -t yona-engine-host -f backtesting_backend/Dockerfile .
```

Run container (use env file at `backtesting_backend/.env`):

```powershell
docker run --rm -p 8203:8203 --env-file backtesting_backend/.env -v ${PWD}\backtesting_backend\logs:/app/logs yona-engine-host
```

Or use docker-compose (recommended for local development):

```powershell
cd backtesting_backend
docker compose up --build
```

Notes
- The container reads environment variables from `backtesting_backend/.env` when using `docker-compose`.
- Logs are written to `/app/logs`, mounted to the host at `backtesting_backend/logs`.
- Default Engine Host port is `8203` (change via `ENGINE_HOST_PORT` env var).
