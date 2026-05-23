# DB Allocation Utility

Web app to import, manage, and export database allocation Excel spreadsheets.

| Service    | Default port |
|------------|--------------|
| Frontend   | 3000         |
| Backend API| 8080         |
| PostgreSQL | 5432 (local) / 5433 (Docker) |

Ports are configured in `backend/.env` (`API_PORT`, `FRONTEND_PORT`, `DB_PORT`).

## Quick start (one command)

### macOS / Linux

From the project root:

```bash
chmod +x scripts/start-local.sh scripts/stop-local.sh
./scripts/start-local.sh
```

Options:

```bash
./scripts/start-local.sh --docker      # start Postgres via Docker (host port 5433)
./scripts/start-local.sh --skip-deps   # skip uv/yarn install on restart
./scripts/stop-local.sh                # stop background processes
```

### Windows

#### Install prerequisites (one-time)

Run as **Administrator** (recommended) from the project root:

```cmd
scripts\install-windows-prerequisites.cmd
```

Or in PowerShell:

```powershell
.\scripts\install-windows-prerequisites.ps1
```

This uses **winget** to install Node.js LTS, Yarn (via corepack), Python 3.12, uv, and either **Docker Desktop** or **PostgreSQL** (interactive prompt). Options:

```powershell
.\scripts\install-windows-prerequisites.ps1 -All -Database docker   # no prompts, Docker for DB
.\scripts\install-windows-prerequisites.ps1 -All -Database postgres
.\scripts\install-windows-prerequisites.ps1 -Help
```

Requires [App Installer / winget](https://aka.ms/getwinget). After install, **open a new terminal** so PATH updates apply.

Manual installs: [Node.js](https://nodejs.org/) + Yarn, [Python 3.12+](https://www.python.org/), [uv](https://docs.astral.sh/uv/), PostgreSQL **or** [Docker Desktop](https://www.docker.com/products/docker-desktop/), PowerShell 5.1+ (or [PowerShell 7](https://github.com/PowerShell/PowerShell)).

#### Local PostgreSQL on Windows (recommended if you installed Postgres)

One-time setup — finds `psql` under `Program Files\PostgreSQL`, writes `backend\.env`, creates the database:

```cmd
scripts\setup-local-postgres.cmd
```

You will be prompted for the **postgres** user password you chose during PostgreSQL installation.

> **Note:** On Windows, use `psql --version` (not `postgres --version`). The setup script finds `psql` under `C:\Program Files\PostgreSQL\*\bin` automatically. If your project path contains spaces (e.g. OneDrive), use the latest scripts from git — they load `scripts\windows-postgres-helpers.ps1` (not `scripts\lib\`, which is excluded from git).

Start the app (uses port **5432**, does not start Docker):

```cmd
scripts\start-local-postgres.cmd
```

```powershell
.\scripts\setup-local-postgres.ps1 -Password "your-postgres-password"
.\scripts\start-local.ps1 -LocalPostgres
```

#### Run the app (all options)

From the project root in **Command Prompt** or **PowerShell**:

```cmd
scripts\start-local-postgres.cmd
```

Or the generic starter (local Postgres by default; use `-Docker` for Docker):

```cmd
scripts\start-local.cmd
```

Options:

```powershell
.\scripts\start-local.ps1 -LocalPostgres   # default — local PostgreSQL on 5432
.\scripts\start-local.ps1 -Docker          # Postgres via Docker (host port 5433)
.\scripts\start-local.ps1 -SkipDeps        # skip uv/yarn install on restart
.\scripts\stop-local.ps1                   # stop processes
```

```cmd
scripts\stop-local.cmd
```

The script opens two terminal windows (Backend and Frontend). Logs are also written under `.local\logs\`.

If PowerShell blocks scripts, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

---

This will create `backend/.env` if needed, ensure the database exists, run migrations, install dependencies, and start the API and frontend.

Open http://localhost:3000 — register a user, then upload `tmp/DB_Excel_Utility_dummy_list.xlsx` from the Databases page.

### Manual setup

### 1. Start PostgreSQL

```bash
docker compose up -d   # exposes Postgres on host port 5433
```

For Docker, set `DB_PORT=5433` in `backend/.env`. For a local Postgres install, use `DB_PORT=5432`.

### 2. Backend

Configure `backend/.env` (see `.env.example`):

```
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=password
DB_NAME=db_allocation
API_PORT=8080
FRONTEND_PORT=3000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

```bash
cd backend
cp .env.example .env   # if .env does not exist
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8080
```

### Database migrations (Alembic)

Migrations live in `backend/alembic/versions/` with dated filenames: `YYYY_MM_DD_<revision>_<slug>.py`.

```bash
cd backend
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
uv run alembic downgrade -1
```

If the database already had tables created before Alembic, stamp the current revision once:

```bash
uv run alembic stamp head
```

### 3. Frontend

```bash
cd frontend
yarn
yarn dev --port 3000
```

## Email via Microsoft Outlook

Most corporate tenants (including Alight) **disable SMTP username/password** with error `5.7.139 basic authentication is disabled`. Use **Microsoft Graph** instead:

### Option A — Microsoft Graph (recommended)

1. In [Azure Portal](https://portal.azure.com) → **Microsoft Entra ID** → **App registrations** → **New registration**.
2. Note **Application (client) ID** and **Directory (tenant) ID**.
3. **Certificates & secrets** → New client secret → copy the value.
4. **API permissions** → Add permission → **Microsoft Graph** → **Application permissions** → **Mail.Send** → **Grant admin consent** (requires admin).
5. Add to `backend/.env`:

```env
EMAIL_ENABLED=true
EMAIL_PROVIDER=graph
MAIL_FROM=you@alight.com
GRAPH_SEND_AS=you@alight.com
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=your-secret-value
```

6. Restart the backend. `GRAPH_SEND_AS` is the mailbox that sends mail (your work email).

### Option B — SMTP (only if IT enables SMTP AUTH)

```env
EMAIL_ENABLED=true
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=you@yourcompany.com
SMTP_PASSWORD=your-app-password
MAIL_FROM=you@yourcompany.com
```

If you see **5.7.139**, SMTP is blocked — switch to Option A.

### In the UI

| Action | Where |
|--------|--------|
| Email assignee about one database | Databases → **Email** on a row |
| Email expiring list | Databases → filter by expiration → **Email expiry list** |
| Email KPI report | Home → click KPI → **Email report** |
| Custom email | Databases → **Send email** |

Assignee column can be a plain email (`user@company.com`) or `Name <user@company.com>`.

## Logging

Logs are prefixed for easy filtering:

| Prefix | Where |
|--------|--------|
| `[BE]` | Backend (Python) — console, `.local/logs/api.log`, `.local/logs/backend.log` |
| `[FE]` | Frontend (browser devtools console) and `.local/logs/frontend.log` when using `start-local.sh` |

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Set to `DEBUG` for SQL queries and request bodies |
| `LOG_FILE` | `.local/logs/api.log` | Backend log file (relative to project root) |
| `LOG_REQUEST_BODY` | `true` | Log JSON request bodies (passwords redacted) |

Each API request gets an `X-Request-ID` — on errors, the UI shows it so you can grep `[BE]` logs for that id.

## Features

- **Excel import** — same column layout as the source spreadsheet
- **Excel export** — `DB_Excel_Utility_list_YYYY-MM-DD.xlsx`
- **CRUD** — edit every uploaded field inline; delete records
- **KPIs (home)** — expiring this month (End Date), prod mirror count, totals
- **Auth** — registration and login (JWT)
- **Email (Outlook)** — notify assignees, email KPI/expiry reports, custom messages
- **About** page

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register |
| POST | `/api/auth/login` | Login (form: username=email, password) |
| GET | `/api/databases/kpis` | Dashboard KPIs |
| GET | `/api/databases` | List records |
| PATCH | `/api/databases/{id}` | Update record |
| DELETE | `/api/databases/{id}` | Delete record |
| DELETE | `/api/databases/clear/all?confirm=true` | Delete all database records |
| POST | `/api/databases/import` | Upload `.xlsx` (`?replace=true` to replace all) |
| GET | `/api/databases/export/excel` | Download Excel |
| GET | `/api/email/status` | Email / SMTP configuration status |
| POST | `/api/email/send` | Send custom email |
| POST | `/api/email/records/{id}/notify` | Email assignee about a record |
| POST | `/api/email/expiry-digest` | Email KPI category report |

## Project layout

```
backend/          # FastAPI + SQLAlchemy
frontend/         # React + Vite
docker-compose.yml
tmp/              # Sample Excel (gitignored)
```
