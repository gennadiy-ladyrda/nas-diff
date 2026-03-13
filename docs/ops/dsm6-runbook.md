# DSM6 Runbook (OPS-01)

## 1. Scope
This runbook covers installation, operations, update, backup/restore, and troubleshooting for `nas-diff` on Synology DSM6 (`x86`) in a single-node LAN setup.

## 2. Safety Defaults
- Default action: `move_to_trash`.
- `delete_permanent` is blocked unless `HARD_DELETE_ENABLED=true`.
- Never enable hard delete without an explicit maintenance window and backup.

## 3. Prerequisites
- DSM6 host with Container Manager / Docker Compose support.
- Access to NAS paths that will be mounted into `/nas`.
- `docker`, `docker compose`, and `just` available in shell.
- Clone path for repository, example: `/volume1/docker/nas-diff`.

## 4. Required Paths and Permissions
1. Host data directory for SQLite and service data:
- default: `${HOME}/.nas-diff/data`
- must be writable by container user.

2. NAS scan roots mounted to `/nas`:
- example host path: `/volume1/photo`
- in container becomes `/nas/photo`.

3. Trash directory:
- default in container: `/nas/.nas-diff-trash`
- must allow create/rename/write operations.

Permission quick check:
```bash
just config
just up
just health
```
If health is degraded because of file-system errors, fix ownership/ACL before running scans.

## 5. Initial Install (Clean Host)
1. Configure env file:
```bash
cp .env.example .env.local
```
Adjust values in `.env.local`:
- `NAS_MOUNT_PATH`
- `HOST_DATA_DIR`
- `NAS_SCAN_ROOTS`
- `NAS_TRASH_DIR`
- keep `DEFAULT_FILE_ACTION=move_to_trash`
- keep `HARD_DELETE_ENABLED=false`

2. Bootstrap and start:
```bash
just up
just ps
just health
```

3. Open services:
- API: `http://<NAS_HOST>:18080/docs`
- UI: `http://<NAS_HOST>:15173`

## 6. Routine Operations
### Start
```bash
just up
```

### Stop
```bash
just down
```

### Service status
```bash
just ps
```

### Logs
```bash
just logs api
just logs worker
just logs frontend
just logs redis
```

### Effective compose config
```bash
just config
```

## 7. Update Procedure
1. Pull new code in repository.
2. Review `.env.local` for newly added variables.
3. Rebuild and restart:
```bash
just up
```
4. Verify:
```bash
just ps
just health
```
5. Check API schema and smoke workflow in UI.

## 8. Backup and Restore

### 8.1 Backup (SQLite + Redis AOF)
Run from repository root:
```bash
mkdir -p backups
TS="$(date +%Y%m%d-%H%M%S)"
cp "${HOST_DATA_DIR:-$HOME/.nas-diff/data}/nas_diff.db" "backups/nas_diff-${TS}.db"
docker compose --env-file .env.local exec -T redis redis-cli SAVE >/dev/null
docker compose --env-file .env.local cp redis:/data/appendonly.aof "backups/appendonly-${TS}.aof"
```

### 8.2 Restore SQLite
1. Stop services:
```bash
just down
```
2. Restore snapshot:
```bash
cp backups/nas_diff-<timestamp>.db "${HOST_DATA_DIR:-$HOME/.nas-diff/data}/nas_diff.db"
```
3. Start and verify:
```bash
just up
just health
```

### 8.3 Restore Redis AOF (Queue State)
Use only if queue persistence is needed after incident:
1. Stop services: `just down`.
2. Restore file into Redis volume:
```bash
docker compose --env-file .env.local up -d redis
docker compose --env-file .env.local cp backups/appendonly-<timestamp>.aof redis:/data/appendonly.aof
docker compose --env-file .env.local restart redis
```
3. Start full stack: `just up`.

## 9. Troubleshooting
### Case A: `database is locked`
Symptoms:
- API returns sqlite lock errors.

Actions:
1. Check parallel write spikes in logs: `just logs api` and `just logs worker`.
2. Ensure there is only one worker service instance.
3. Restart stack: `just down && just up`.
4. If still failing, restore latest SQLite backup.

### Case B: Redis unavailable
Symptoms:
- health endpoint has `redis=error`.
- scan/action jobs stay in queued state.

Actions:
1. Check container status: `just ps`.
2. Review redis logs: `just logs redis`.
3. Restart redis: `docker compose --env-file .env.local restart redis`.
4. Re-check `just health`.

### Case C: `permission denied` on scan/move
Symptoms:
- action items fail with file-system permission errors.

Actions:
1. Validate mount path from `.env.local` (`NAS_MOUNT_PATH`).
2. Verify read/write rights on scan roots and trash dir at host level.
3. Confirm trash path exists or can be created (`/nas/.nas-diff-trash`).
4. Re-run a small batch with `move_to_trash` only.

## 10. Dry-Run Acceptance Checklist
1. Stack starts from clean host by runbook commands only.
2. `GET /api/v1/health` returns `status=ok`.
3. UI opens and can start one scan.
4. Backup command creates SQLite and AOF snapshots.
5. Restore SQLite and verify API still reports healthy status.
