# Deployment

## Architecture

Run the central services with Docker Compose:

- `db`: PostgreSQL with a persistent named volume.
- `backend`: FastAPI API with a persistent screenshot volume.
- `frontend`: production React build served by Nginx.

Run the desktop agent natively on each employee Windows computer. It must not
run in Docker because it needs access to that computer's screen, input events,
foreground applications, lock state, and sleep/wake state.

## Local Docker deployment

From the `New project` directory:

```powershell
Copy-Item .env.docker.example .env.docker
notepad .env.docker
# Replace both placeholder secrets.
docker compose --env-file .env.docker up -d --build

docker compose exec backend python create_admin.py
```

Open `http://localhost:8080`. The API health endpoint is
`http://localhost:8000/health`.

Useful commands:

```powershell
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f backend
docker compose --env-file .env.docker down
docker compose --env-file .env.docker down -v  # destroys database and screenshots
```

Do not use `down -v` unless the stored data has been backed up.

## Production deployment

1. Provision a server with Docker and a firewall.
2. Copy `.env.docker.example` to `.env.docker` and set strong unique secrets.
3. Set `PUBLIC_BACKEND_URL` to the HTTPS API URL used by browsers and agents,
   such as `https://api.tracker.example.com`.
4. Set `ALLOWED_ORIGINS` to the HTTPS dashboard origin only, such as
   `https://tracker.example.com`.
5. Put a TLS reverse proxy in front of the frontend and backend, or expose them
   through your existing HTTPS gateway.
6. Run the Compose stack and verify `/health`.
7. Back up the `tracker_db` and `tracker_screenshots` volumes.
8. Build the Windows agent on Windows:

```powershell
cd desktop-agent
.\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-build.txt
.\build-agent.bat
```

9. Distribute `desktop-agent\dist\OrgTrackerAgent.exe` and a side-by-side
   `.env` containing the central HTTPS API URL:

```text
BACKEND_URL=https://api.tracker.example.com
SCREENSHOT_INTERVAL_SECONDS=300
IDLE_TIMEOUT_SECONDS=300
MEDIA_ACTIVITY_DETECTION_ENABLED=true
LONG_RUNNING_ACTIVITY_DETECTION_ENABLED=true
SYSTEM_STATE_DETECTION_ENABLED=true
```

10. Install the agent in Windows Startup on each employee computer and have
    each employee log in with the account created by an administrator.

## Operational requirements

- Use HTTPS before sending credentials or screenshots over a network.
- Do not use the example JWT secret or a weak database password.
- Restrict dashboard access and define screenshot retention/deletion rules.
- Obtain the required employee notice and consent for monitoring in the
  jurisdictions where the system will operate.
- Test lock, sleep, video playback, downloads, long-running scripts, and remote
  desktop sessions on a real Windows machine before rollout.

## Production checklist

- Set `JWT_SECRET_KEY` and `POSTGRES_PASSWORD` to unique secrets.
- Put the frontend and API behind a TLS reverse proxy and set
   `PUBLIC_BACKEND_URL` and `ALLOWED_ORIGINS` to HTTPS origins.
- Back up both `tracker_db` and `tracker_screenshots` volumes on a schedule.
- Create organizations first, then create managers and employees under the
   correct organization/team from the dashboard.
- Configure retention and masking in Tracker Management and publish the
   current monitoring/consent policy before enabling agents.
- Build the Windows agent on Windows with `build-agent.bat`, copy the `.env`
   beside the executable, and install startup on each device.
- Test recovery by stopping the API briefly and confirming queued screenshots
   upload after the API returns.
