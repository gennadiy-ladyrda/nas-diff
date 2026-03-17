# DSM6 Runbook (OPS-01)

## 1. Scope
This runbook covers installation, operations, update, backup/restore, and troubleshooting for `nas-diff` on Synology DSM 6.1.4 (`x86_64`) in a single-node LAN setup.

## 2. Safety Defaults
- Default action: `move_to_trash`.
- `delete_permanent` is blocked unless `HARD_DELETE_ENABLED=true`.
- Never enable hard delete without an explicit maintenance window and backup.

## 3. Prerequisites
- DSM 6.1.4 host with Synology `Docker` package and `docker-compose` support.
- Access to NAS paths that will be mounted into `/nas`.
- `docker`, `docker compose`, and `just` available in shell.
- Clone path for repository, example: `/volume1/docker/nas-diff`.

Validated host facts for the current package target:
- model: `DS3615xs-j`
- architecture: `x86_64`
- DSM: `6.1.4-15217 Update 1`
- Synology Docker package: `20.10.3-0554`
- runtime compose binary on DSM host: `/usr/local/bin/docker-compose`

Important compatibility notes:
- Package lifecycle scripts must not assume the same `PATH` as an interactive SSH session.
- `docker-compose` on the validated DSM host is `1.28.5`, so package compose manifests must avoid nested interpolation in `image:` fields.
- Offline bundled images for `.spk` must be `linux/amd64`; otherwise containers fail with `exec format error`.

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

## 7A. Synology Package Build (DSM 6.1.4 `.spk`)
Use this flow when building the Package Center artifact instead of running plain `docker-compose`.

Detailed offline handoff with exact commands:
- `docs/ops/dsm6-package-build-handoff.md`

### Preferred local build path
For the current DSM 6.1.4 package, the fastest reproducible path is a toolkit-compatible manual assembly:
```bash
just spk-build-manual linux/amd64
```

Resulting artifact:
```text
artifacts/synology-spk/nas-diff-x64-0.1.0-0008.spk
```

This path still uses the same staged package layout and bundled offline container images, but does not wait for a full Synology Toolkit build env download.
The packer writes GNU tar compatible archives to avoid DSM Package Center rejecting macOS-built `pax` archives as invalid format, and bundles `linux/amd64` images to match DSM 6.1 `x86_64` hosts.
The package start flow force-recreates containers so that an updated package does not keep running stale wrong-arch container instances from a previous install.

### Prerequisites
- Synology Toolkit installed on the build host.
- Valid DSM6 platform environment inside toolkit, for example `ds.bromolow-6.1`.
- Docker daemon available for bundling `api`, `frontend`, and `redis` images.

### 1. Validate toolkit path and platform
```bash
just spk-check /path/to/toolkit bromolow
```

This command verifies:
- toolkit root;
- `pkgscripts-ng/PkgCreate.py`;
- `build_env/ds.<platform>-6.1`;
- writable `source/` and `result_spk/`.

### 2. Stage package with bundled images
```bash
just spk-stage-images
```

This prepares a toolkit-compatible project tree and bundles offline image archives into `payload/images/`.

### 3. Build `.spk`
```bash
just spk-build-images /path/to/toolkit bromolow
```

Default behavior passes `--no-sign`. Resulting artifact is expected under:
```text
<toolkit>/result_spk/
```

Optional Dockerized Toolkit path:
```bash
just spk-build-docker bromolow
```

### 4. What to verify after build
- `.spk` exists in `result_spk/`.
- `INFO` reflects expected `version`, `adminport`, and `dsmuidir`.
- `package.tgz` contains:
  - `runtime/`
  - `ui/`
  - `images/`
  - `port_conf/`

### 5. Expected current limitation
The repository now builds a real `.spk` artifact and prepares lifecycle scaffold, but full install/start validation still requires a real DSM 6.1.4 NAS host.

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

### Case D: `exec format error`
Symptoms:
- all containers restart immediately;
- `docker logs nas-diff-api` or `docker logs nas-diff-frontend` show `exec user process caused: exec format error`.

Actions:
1. Confirm image architecture on the build host before packaging.
2. Rebuild the package with `linux/amd64` bundled images:
```bash
just spk-build-manual linux/amd64
```
3. Install the new `.spk` over the old package.
4. Start the package again; runtime scripts already use `--force-recreate` to replace old container instances.

## 10. Dry-Run Acceptance Checklist
1. Stack starts from clean host by runbook commands only.
2. `GET /api/v1/health` returns `status=ok`.
3. UI opens and can start one scan.
4. Backup command creates SQLite and AOF snapshots.
5. Restore SQLite and verify API still reports healthy status.
