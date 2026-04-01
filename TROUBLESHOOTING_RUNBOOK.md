# Server Troubleshooting Runbook

Database, Software, and Network checks for HMS (192.168.2.216 and local).

---

## 0. "Server not working" – quick fix (192.168.2.216)

**Symptom:** Cannot reach http://192.168.2.216:8000 (connection refused).

**Cause:** Nothing is listening on port 8000 on that machine.

**Do this ON the server (192.168.2.216):**

1. **Start Django** (bind to all interfaces so other PCs can connect):
   ```bash
   cd path\to\chm
   python manage.py runserver 0.0.0.0:8000
   ```
   Or double‑click **RUN_ON_SERVER_192.168.2.216.bat** (after copying the project to the server).

2. **If the DB is on the same server:** Start PostgreSQL first (e.g. start the service, or `docker-compose up -d db` if you use Docker).

3. **If Windows Firewall blocks port 8000:** Run **allow_port_8000_firewall.bat** as Administrator, or add an inbound rule for TCP 8000.

After step 1, try again: http://192.168.2.216:8000

---

## 1. Quick check (run from project root)

```bash
python manage.py troubleshoot_server --host 192.168.2.216 --port 8000
```

- **Database**: connection, engine, screening tables, pending migrations  
- **Application**: DEBUG, ALLOWED_HOSTS, cache, URL reverse  
- **Network**: host resolution, TCP connect to host:port  

Skip network when DB is remote and you only want DB/app:

```bash
python manage.py troubleshoot_server --skip-network
```

---

## 2. Database engineer checklist

| Check | Command / Action |
|-------|------------------|
| **Connection** | `python manage.py dbshell` then `SELECT 1;` |
| **PostgreSQL version** | In dbshell: `SELECT version();` |
| **Pending migrations** | `python manage.py showmigrations hospital` — look for `[ ]` |
| **Apply migrations** | `python manage.py migrate hospital` |
| **Screening tables** | In dbshell: `\dt hospital_screening*` (or run `troubleshoot_server`) |
| **Env** | Ensure `DATABASE_URL` in `.env` (e.g. `postgresql://user:pass@host:5432/dbname`) |
| **Remote DB** | From server: `psql $DATABASE_URL` or `telnet <db_host> 5432` |

**Typical fixes**

- Connection refused → PostgreSQL not running or wrong host/port.
- "relation does not exist" → Run `python manage.py migrate hospital`.
- Timeout → Firewall, wrong host/port, or DB server down.

---

## 3. Software engineer checklist

| Check | Command / Action |
|-------|------------------|
| **Config** | `python manage.py check` |
| **DEBUG** | In production prefer `DEBUG=False`; set via `.env` / env vars. |
| **ALLOWED_HOSTS** | Must include server IP/hostname (e.g. `192.168.2.216`). In DEBUG, private IPs are often allowed. |
| **Static files** | `python manage.py collectstatic --noinput` (if used). |
| **Start app** | `python manage.py runserver 0.0.0.0:8000` — **0.0.0.0** so other hosts can connect. |
| **Gunicorn** | `gunicorn --bind 0.0.0.0:8000 hms.wsgi:application` |
| **URLs** | If `/hms/screening/` 404s, ensure latest `hospital/urls.py` and `hms/urls.py` are deployed (screening routes). |
| **Logs** | Check stdout/stderr of runserver or gunicorn; check systemd/journal if applicable. |

**Typical fixes**

- 404 for `/hms/screening/` → Deploy updated `hospital/urls.py` and/or `hms/urls.py` (screening routes).
- "Invalid HTTP_HOST" → Add host to `ALLOWED_HOSTS` or use DEBUG with private IP.
- "Connection refused" from browser → App not running or bound to `127.0.0.1` only; use `0.0.0.0:8000`.

---

## 4. Network engineer checklist

**From your PC (client) to server 192.168.2.216**

| Check | Windows | Linux/macOS |
|-------|---------|-------------|
| **Ping** | `ping 192.168.2.216` | `ping 192.168.2.216` |
| **TCP port 8000** | `Test-NetConnection -ComputerName 192.168.2.216 -Port 8000` | `nc -zv 192.168.2.216 8000` or `telnet 192.168.2.216 8000` |
| **Traceroute** | `tracert 192.168.2.216` | `traceroute 192.168.2.216` |

**On the server (192.168.2.216)**

| Check | Command |
|-------|--------|
| **Listening on 8000** | `ss -tlnp \| grep 8000` or `netstat -tlnp \| grep 8000` |
| **Firewall (Linux)** | `sudo firewall-cmd --list-ports`; open: `sudo firewall-cmd --add-port=8000/tcp --permanent && sudo firewall-cmd --reload` |
| **Firewall (Windows)** | Allow inbound TCP 8000 in Windows Firewall. |
| **Bind address** | Django/gunicorn must bind to `0.0.0.0:8000`, not `127.0.0.1:8000`, for external access. |

**Interpretation**

- **Ping OK, TCP fail** → Service not listening on 8000 or firewall blocking. Start app with `0.0.0.0:8000` and open port.
- **Ping fail** → Server off, wrong IP, or network/routing issue.
- **TCP OK** → Network path and listener OK; if browser still fails, check ALLOWED_HOSTS and app logs.

---

## 5. One-line summaries

- **Database**: `DATABASE_URL` correct, PostgreSQL up, migrations applied (`migrate hospital`).
- **Software**: App running with `0.0.0.0:8000`, `ALLOWED_HOSTS` includes server IP, latest URLs deployed.
- **Network**: Server reachable (ping), port 8000 open and listening (Test-NetConnection / nc), firewall allows 8000.

---

## 6. Run troubleshoot command from this repo

From project root (e.g. `D:\chm` or on server):

```bash
python manage.py troubleshoot_server --host 192.168.2.216 --port 8000
```

Use `--skip-network` to run only DB and application checks (e.g. when DB is on another host).
