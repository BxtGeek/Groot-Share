# Groot Share

Your files. Your shares. Your control.

Groot Share is a lightweight, self-hosted file management web application built with Python, FastAPI, and Jinja2. It provides a clean, modern interface for browsing, uploading, and managing files across local directories, SMB/CIFS shares, and NFS shares — all mounted on the host and exposed to the container.

## Features

- **Simple, responsive UI** – Clean file manager with drag-and-drop uploads, breadcrumb navigation, sorting, and search
- **Multiple storage backends** – Local directories, SMB/CIFS shares, and NFS shares (mounted on the host)
- **Secure by default** – Single admin login, path traversal protection, read-only enforcement, atomic config writes
- **Docker-first deployment** – Runs as non-root user, health checks, graceful shutdown
- **No heavy frontend frameworks** – Pure HTML, CSS, and vanilla JavaScript

## Quick Start

### 1. Prepare the host

Create a configuration directory and a test storage mount:

```bash
mkdir -p ./config /tmp/groot_test_storage
```

### 2. Configure environment

Copy the example environment file and adjust as needed:

```bash
cp .env.example .env
# Edit .env to set ADMIN_PASSWORD, SESSION_SECRET, etc.
```

### 3. Build and run

```bash
docker compose up -d --build
```

The application will be available at `http://localhost` (port 80 by default) or `http://localhost:8080` if you change the host port mapping.

### 4. Log in

Use the admin password from your `.env` file (default: `admin`).

### 5. Add storage

Go to Settings (gear icon) → "Add Storage" to configure your first storage location.

## Storage Configuration

Groot Share treats all storage as **host-mounted directories**. You must mount SMB/NFS shares on the host first, then bind-mount them into the container.

### Example: Local directory

```yaml
volumes:
  - /srv/my-files:/storage/my-files:rw
```

In Settings, add a "Local" storage with path `/storage/my-files`.

### Example: SMB/CIFS share (mounted on host)

```bash
# On the host (Linux):
sudo mount -t cifs //192.168.1.20/documents /mnt/nas-docs -o username=user,password=pass,uid=1000,gid=1000
```

```yaml
volumes:
  - /mnt/nas-docs:/storage/nas-docs:ro
```

In Settings, add an "SMB" storage with path `/storage/nas-docs`. The server/share fields are stored as metadata.

### Example: NFS share (mounted on host)

```bash
# On the host (Linux):
sudo mount -t nfs 192.168.1.30:/volume1/backups /mnt/nfs-backups
```

```yaml
volumes:
  - /mnt/nfs-backups:/storage/backups:ro
```

In Settings, add an "NFS" storage with path `/storage/backups`.

## Directory Structure

```
/srv/groot/
├── config/              # Configuration (storages.json)
│   └── storages.json    # Storage definitions (owner: 1000:1000, mode: 600)
├── storage/             # Host-mounted storage directories
│   ├── files/           # Local files
│   ├── nas-docs/        # SMB share (mounted on host)
│   └── backups/         # NFS share (mounted on host)
```

## Configuration

All configuration is via environment variables (see `.env.example`). Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_PASSWORD` | `admin` | Administrator password |
| `SESSION_SECRET` | `change-me-in-production` | Session cookie secret |
| `CONFIG_PATH` | `/config/storages.json` | Config file location |
| `MAX_UPLOAD_SIZE_MB` | `2048` | Maximum upload size |
| `PERMITTED_ROOTS` | `/storage` | Allowed mount prefixes (colon-separated) |
| `HOST_PORT` | `80` | Host port in docker-compose |

## Security Notes

- **Always change `ADMIN_PASSWORD` and `SESSION_SECRET`** in production
- Use HTTPS in production (set `SESSION_COOKIE_SECURE=true`)
- The config file `storages.json` is written with `600` permissions
- SMB passwords are stored in the config file (plaintext) — protect the host filesystem
- Path traversal is blocked at the API layer; symlinks are resolved and checked against the storage root
- Read-only enforcement happens server-side, not just in the UI

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard (requires auth) |
| GET | `/login` | Login page |
| POST | `/login` | Submit password |
| GET | `/logout` | Logout |
| GET | `/settings` | Settings page |
| GET | `/health` | Health check |
| GET | `/api/storages` | List storages |
| POST | `/api/storages` | Add storage |
| GET | `/api/storages/{id}` | Get storage (no secrets) |
| PUT | `/api/storages/{id}` | Update storage |
| DELETE | `/api/storages/{id}` | Delete storage config |
| POST | `/api/storages/{id}/test` | Test connection |
| GET | `/api/storages/{id}/browse` | Browse directory |
| POST | `/api/storages/{id}/upload` | Upload file |
| GET | `/api/storages/{id}/download` | Download file |
| POST | `/api/storages/{id}/mkdir` | Create directory |
| POST | `/api/storages/{id}/rename` | Rename item |
| DELETE | `/api/storages/{id}/item` | Delete item |

## Development

### Run locally (without Docker)

```bash
pip install -r groot_share/requirements.txt
export ADMIN_PASSWORD=admin
export SESSION_SECRET=dev-secret
export CONFIG_PATH=./config/storages.json
export PERMITTED_ROOTS=./storage
mkdir -p ./config ./storage
python -m uvicorn groot_share.app.main:app --reload --port 8080
```

### Run tests

```bash
pip install pytest
cd groot_share
python -m pytest tests/ -v
```

## Tests

Automated tests cover:
- Directory browsing and navigation
- File upload, download, rename, delete
- Read-only enforcement
- Path traversal and symlink escape attempts
- Invalid storage IDs
- Authentication

Run with: `pytest tests/ -v`

## License

MIT

## Contributing

PRs welcome. Please keep the codebase minimal and focused on the core file management use case.