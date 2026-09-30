# Monitoring system

A working employee time & activity tracker: a desktop agent that runs on
each employee's machine, a backend API, and an admin web dashboard.

```
┌─────────────────────┐        HTTPS/JSON         ┌──────────────────────┐
│  Desktop Agent       │ ─────────────────────────▶│  Backend API          │
│  (Windows/Mac/Ubuntu)│   login, start/stop,       │  FastAPI + SQLAlchemy │
│  Python + mss +      │   screenshot upload         │  + SQLite/Postgres    │
│  pystray tray icon   │◀───────────────────────────│                       │
└─────────────────────┘        JWT auth            └───────────┬──────────┘
                                                                 │
                                                       stores screenshots
                                                       on disk + metadata
                                                       (user, IP, time entry)
                                                       in the DB
                                                                 │
                                                     ┌───────────▼──────────┐
                                                     │  Admin Dashboard      │
                                                     │  React (Vite)         │
                                                     │  timesheets,          │
                                                     │  screenshot viewer    │
                                                     └───────────────────────┘
```

**Important — one backend, many agents.** For an organization rollout there
is exactly **one** backend (running on a central server) and **one**
dashboard, but the desktop agent runs on **every** employee's machine and
they all point at that same central backend. Don't run a separate backend
per employee — see "Deploying across your organization" below.

## Why this stack

- **Backend: Python + FastAPI** — async REST endpoints, automatic OpenAPI
  docs at `/docs`, and Pydantic validation with very little boilerplate.
  SQLAlchemy + SQLite locally, swap to Postgres in production by changing
  one env var (needed once several employees are writing at once — see
  below).
- **Desktop agent: Python** — has to run natively on Windows, macOS, *and*
  Ubuntu. `mss` does cross-platform screenshotting, `pystray` gives a native
  system tray icon with a Start/Stop menu on all three OSes, and it packages
  into a single .exe with PyInstaller so employees never need Python
  installed.
- **Frontend: React (Vite)** — a small admin SPA that talks to the same
  backend API.

## Project layout

```
backend/          FastAPI server, SQLAlchemy models, JWT auth
desktop-agent/     The tracker that runs on employee machines
frontend/          React admin dashboard (users, timesheets, screenshots)
```

## How the tracking flow works

1. An **admin** logs into the dashboard and creates employee accounts
   (`POST /users`).
2. An **employee** runs the desktop agent and logs in once via a small
   login window — a token is cached locally so this only happens once
   (until the token expires or is cleared).
3. Employee clicks **Start Tracking** in the tray icon:
   - Agent calls `POST /time-entries/start` with its public IP → backend
     opens a `TimeEntry` row (start time, IP, user).
   - A background thread starts a loop.
4. Every 5 minutes (configurable via `SCREENSHOT_INTERVAL_SECONDS`), the
   agent captures the screen, gets the current public IP, and uploads both
   to `POST /screenshots` along with the active time entry ID.
5. Backend saves the image under `backend/storage/screenshots/<user_id>/...`
   and a row in the `screenshots` table (user, time entry, file path, IP,
   timestamp).
6. Employee clicks **Stop Tracking** → `POST /time-entries/{id}/stop` closes
   the entry and records total duration.
7. Admin dashboard reads `/time-entries` and `/screenshots` to show who's
   currently tracking, timesheets, and a screenshot gallery per session.
8. If the agent restarts (PC reboot, crash) while a session was active, it
   re-syncs with the backend on startup (`GET /time-entries/active`) instead
   of losing track of the running session.

## Running it locally (one machine, for development/testing)

Quickest way: after doing the one-time setup below for each of the three
folders, just double-click **`start-all.bat`** at the project root — it
opens three windows (Backend / Frontend / Desktop Agent) at once. The
sections below are that one-time setup, and what each window is actually
running.

**Backend**
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python create_admin.py        # create the first admin login
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API docs: http://localhost:8000/docs

**Desktop agent** (for development — running from source with Python
installed; see "Deploying" below for the packaged .exe employees actually
use)
```bash
cd desktop-agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set BACKEND_URL
python agent.py
```
A small login window opens on first run (or when the saved token is
invalid/expired); after that it's cached and you go straight to the tray
icon.

**Frontend**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
Dashboard: http://localhost:5173 — log in with the admin account you created.

This was smoke-tested end-to-end in this environment: admin creation, login,
start-tracking, screenshot upload, stop-tracking, and listing all worked
against the real FastAPI app. The desktop agent's screenshot capture, and
the login window's actual on-screen appearance, need a real display
(Windows/macOS/Ubuntu desktop session) to fully verify — they can't be
exercised headlessly here, though the same widget-construction code was
verified to run correctly against a live display during development.

### Windows convenience scripts (this folder)

- **`run.bat`** — the one file to double-click. On a brand-new computer (or
  if the venvs are missing/broken — e.g. this folder was copied from
  another machine), it automatically runs setup first, installs Windows
  autostart for this user if it is missing, then starts everything silently
  in the background. On every run after that, it just starts everything in
  a few seconds — no thinking required either way.
- **`setup.bat`** — what `run.bat` calls automatically when needed. Creates
  fresh `venv` folders for the backend and desktop agent and installs all
  dependencies, using whichever Python/Node.js are already installed on
  that machine. You can also run it directly if you want to force a clean
  rebuild.
- **`start-all.bat`** — opens backend/frontend/agent each in their own
  visible console window instead of silently — useful for development, so
  you can see the logs.
- **`start-all-background.vbs`** (launched via `start-all-background.bat`,
  which is what `run.bat` uses) — starts the same three things silently,
  with no visible windows.
- **`install-local-autostart.bat`** / **`uninstall-local-autostart.bat`** —
  manually adds/removes the same Startup-folder shortcut that `run.bat`
  now installs automatically, so the whole stack (backend, dashboard, and
  agent) launches automatically when this Windows user logs in.
- **`stop-all.bat`** — stops any backend/frontend/agent processes that were
  started from this project folder.

### Moving this project to a different computer

**Do not copy the `venv` folders (`backend\venv`, `desktop-agent\venv`) or
`frontend\node_modules` to another computer** — e.g. don't include them in
a zip you upload/transfer. A Python virtual environment hardcodes the exact
file path of the Python installation that created it; on a different
computer (or even the same computer with Python reinstalled elsewhere),
that path won't exist and every script that uses it will fail with an
error like:

```
Python Launcher is sorry to say ...
No Python at 'C:\Users\<name>\AppData\Local\Python\pythoncore-3.12-64\pythonw.exe'
```

To move this project correctly:
1. Copy everything **except** `backend\venv`, `desktop-agent\venv`, and
   `frontend\node_modules` (in File Explorer, select all files/folders
   except those three before zipping/copying — this also keeps the
   transfer far smaller than including them).
2. On the destination computer, double-click **`run.bat`**. It notices the
   venvs are missing, runs setup automatically, then starts everything —
   no separate steps needed. (If you'd rather do it manually, run
   `setup.bat` yourself first, then `start-all.bat`.)

### The backend port — one setting, never hardcoded per machine

`backend\.env`'s `PORT` value is the **only** place the backend's port is
ever set. `desktop-agent\.env` and `frontend\.env` don't have their own
independent port setting — every time `setup.bat` runs (including
automatically, via `run.bat`), it reads `PORT` from `backend\.env` and
rewrites the `localhost:<port>` portion of `BACKEND_URL` /
`VITE_BACKEND_URL` in those two files to match, on whatever computer it's
running on. `start-all-background.vbs` and `start-backend.bat` also read
`PORT` from `backend\.env` directly instead of hardcoding a number.

This means: if port 8000 is already taken by something else on a
particular machine, change `PORT` in that machine's `backend\.env` and
re-run `setup.bat` (or just `run.bat`) — every other component
automatically follows, on that machine only. It also means you should
never edit a port number directly inside `start-backend.bat` or
`start-all-background.vbs` — change it in `backend\.env` instead, or the
next `setup.bat` run will overwrite your edit back to whatever
`backend\.env` says.

(This is the fix for a real bug hit during development: two launcher
scripts once had a hardcoded port that didn't match the `.env.example`
templates, so a fresh clone on a different computer had the agent silently
unable to reach the backend — the login window would appear, but nothing
would happen after entering credentials, with no visible error since the
agent runs without a console window. That specific failure mode is why the
port is now centralized instead of repeated in multiple files.)

## Deploying across your organization

The recommended central deployment is Docker Compose. Follow
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) to run PostgreSQL, the backend, and
the production dashboard together. The desktop agent remains a native Windows
executable on each employee computer because it needs access to that
computer's screen, input, foreground applications, lock state, and sleep/wake
state.

This is the part that turns the local demo above into something installed
on every employee's PC. Three phases:

### 1. Stand up the central backend (once)

Pick one machine or server that will run the backend permanently and that
every employee's PC can reach over the network (your office LAN, a VPN, or
a small cloud VM if people work remotely).

- Follow the backend setup above on that machine, but:
  - Switch `DATABASE_URL` in `.env` to Postgres, not SQLite — SQLite can hit
    "database is locked" errors once multiple employees' screenshots are
    landing at overlapping times. Install Postgres, then:
    `DATABASE_URL=postgresql://user:password@localhost:5432/tracker`
    (uncomment `psycopg2-binary` in `requirements.txt` first).
  - Set a real, random `JWT_SECRET_KEY` — never ship the example value.
  - Set `ALLOWED_ORIGINS` in `.env` to your dashboard's real URL instead of
    `*`, e.g. `ALLOWED_ORIGINS=https://tracker.yourcompany.com`.
  - Run uvicorn bound to all interfaces so other machines can reach it:
    `uvicorn app.main:app --host 0.0.0.0 --port 8000` (drop `--reload` in
    production — it's a dev convenience).
  - Open port 8000 (or whichever you choose) in that machine's firewall.
  - Strongly recommended: put this behind a reverse proxy (nginx/Caddy) with
    a real HTTPS certificate, so credentials and screenshots aren't sent in
    plaintext across your network. This isn't set up for you here — it
    depends on your domain/hosting choice.

### 2. Build and distribute the desktop agent

On a Windows dev machine, with the venv active:
```bash
cd desktop-agent
pip install -r requirements.txt -r requirements-build.txt
build-agent.bat
```
This produces `dist\OrgTrackerAgent.exe` — a single file, no Python
required on employee machines.

For each employee's PC:
1. Copy `OrgTrackerAgent.exe` into a permanent folder (e.g.
   `C:\Program Files\OrgTracker\`).
2. Copy a `.env` file into that **same folder**, containing your real
   central backend's address:
   ```
   BACKEND_URL=https://tracker.yourcompany.com
   SCREENSHOT_INTERVAL_SECONDS=300
   ```
   (This is the one thing that has to be correct per-deployment — copy the
   same `.env` to every machine since they all point at the same backend.)
3. Run `install-autostart.bat` from that same folder once — this adds a
   launcher to that Windows user's Startup folder so the agent starts
   automatically every time they log in, with no manual step after that.
   (`uninstall-autostart.bat` reverses it.)
4. On first launch, the employee sees a small login window and logs in with
   the account an admin created for them. After that, the login is cached
   (in `%APPDATA%\OrgTracker\auth_token.json`) and won't ask again until it
   expires.

macOS/Ubuntu: PyInstaller can build for those OSes too (run `build-agent.bat`'s
`pyinstaller --onefile --noconsole --name OrgTrackerAgent agent.py` command
on a Mac/Linux machine instead of Windows — PyInstaller isn't cross-compiling,
you build on the OS you're targeting). Auto-start on those platforms uses a
different mechanism (a `launchd` LaunchAgent on macOS, a `.desktop` autostart
entry or systemd `--user` service on Ubuntu) — not scripted here yet, but
the agent itself already runs on both without changes.

### 3. Build and host the dashboard

Running `npm run dev` forever isn't meant for production. Build it once and
serve the static output:
```bash
cd frontend
# point this at your real central backend before building:
echo "VITE_BACKEND_URL=https://tracker.yourcompany.com" > .env
npm run build      # outputs frontend/dist/
```
Serve `frontend/dist/` with any static file host — nginx, Caddy, or even
a simple `npx serve dist`. Give managers/admins that URL to log in from any
browser.

### Rollout checklist

- [ ] Central backend running on a reachable server, with Postgres, a real
      `JWT_SECRET_KEY`, and `ALLOWED_ORIGINS` restricted to the dashboard URL.
- [ ] HTTPS in front of the backend (reverse proxy) — not done for you here.
- [ ] `OrgTrackerAgent.exe` built and distributed with a `.env` pointing at
      the real backend URL (not `localhost`).
- [ ] `install-autostart.bat` run on each employee machine.
- [ ] Dashboard built (`npm run build`) and hosted somewhere reachable by
      managers, pointed at the real backend URL.
- [ ] Employee accounts created (admin, via `/docs` for now — see gaps below).
- [ ] Employees notified/consented per "Legal/compliance" below — do this
      **before** distributing the agent, not after.

## Important: legal/compliance before you deploy this

Screen capture + IP logging of employees is regulated in most
jurisdictions. Before rolling this out to real staff:

- **Disclose it.** Tell employees monitoring is happening, what's captured,
  and how it's used — ideally have them sign an acknowledgment. Silent
  monitoring is illegal in a number of countries/states (e.g. several US
  states require notice; India's IT Act and various EU/GDPR rules impose
  similar obligations if you have staff there).
- **Limit scope.** Only capture during active work sessions the employee
  started themselves (which is what this design does — nothing happens
  until they click Start).
- **Secure the data.** Screenshots can contain passwords, personal chats,
  banking info, etc. Encrypt at rest, restrict who in the dashboard can view
  them, and set a retention/deletion policy.
- **Check local counsel** if you operate in multiple countries — monitoring
  law varies a lot by state/country.

## What's intentionally left out (natural next steps)

- A signed installer (current packaging is a plain .exe — Windows
  SmartScreen may warn on first run since it's unsigned; code-signing
  removes that warning but requires a certificate).
- Blurring/redacting sensitive screen regions before upload.
- macOS/Ubuntu auto-start scripts (the agent runs on both; the auto-start
  wiring above is Windows-only so far).
- Retry/queueing for screenshot uploads that fail (e.g. backend briefly
  unreachable) — currently that interval's screenshot is just lost.
- A proper "Add Employee" page in the dashboard (currently via `/docs`).
- Projects/tasks assignment, weekly reports, activity-level (mouse/keyboard)
  scoring — the `activity_level` column already exists on `Screenshot` for
  this.
- Password reset / employee self-registration flows.

 
