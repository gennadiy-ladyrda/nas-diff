PRAGMA foreign_keys = ON;

-- Технические настройки и feature flags
CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Источник данных для сканов
CREATE TABLE IF NOT EXISTS scan_roots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Запуски задач сканирования
CREATE TABLE IF NOT EXISTS scan_jobs (
  id TEXT PRIMARY KEY,                          -- UUID
  mode TEXT NOT NULL CHECK (mode IN ('exact', 'similar', 'both')),
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'canceled')),
  requested_at TEXT NOT NULL DEFAULT (datetime('now')),
  started_at TEXT,
  finished_at TEXT,
  error_message TEXT,
  files_seen INTEGER NOT NULL DEFAULT 0,
  files_indexed INTEGER NOT NULL DEFAULT 0,
  exact_groups_found INTEGER NOT NULL DEFAULT 0,
  similar_groups_found INTEGER NOT NULL DEFAULT 0,
  reclaimable_bytes INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scan_job_roots (
  job_id TEXT NOT NULL,
  root_id INTEGER NOT NULL,
  PRIMARY KEY (job_id, root_id),
  FOREIGN KEY (job_id) REFERENCES scan_jobs(id) ON DELETE CASCADE,
  FOREIGN KEY (root_id) REFERENCES scan_roots(id) ON DELETE RESTRICT
);

-- Базовая информация о файлах
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  root_id INTEGER NOT NULL,
  rel_path TEXT NOT NULL,                       -- путь относительно scan_root
  abs_path TEXT NOT NULL UNIQUE,
  file_name TEXT NOT NULL,
  extension TEXT,
  mime_type TEXT,
  size_bytes INTEGER NOT NULL,
  mtime_epoch_ns INTEGER NOT NULL,
  ctime_epoch_ns,
  inode INTEGER,
  dev INTEGER,
  width INTEGER,
  height INTEGER,
  exif_datetime_original TEXT,
  exif_make TEXT,
  exif_model TEXT,
  first_seen_job_id TEXT,
  last_seen_job_id TEXT,
  is_present INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (root_id) REFERENCES scan_roots(id) ON DELETE RESTRICT,
  FOREIGN KEY (first_seen_job_id) REFERENCES scan_jobs(id) ON DELETE SET NULL,
  FOREIGN KEY (last_seen_job_id) REFERENCES scan_jobs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_files_root_rel_path ON files(root_id, rel_path);
CREATE INDEX IF NOT EXISTS idx_files_size ON files(size_bytes);
CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime_epoch_ns);

-- Хэши и отпечатки
CREATE TABLE IF NOT EXISTS file_hashes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL,
  hash_type TEXT NOT NULL CHECK (hash_type IN ('blake3_full', 'dhash64', 'phash64')),
  hash_hex TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (file_id, hash_type),
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_file_hashes_lookup ON file_hashes(hash_type, hash_hex);

-- Группы exact-дубликатов
CREATE TABLE IF NOT EXISTS exact_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  signature TEXT NOT NULL,                      -- например blake3_full
  file_count INTEGER NOT NULL,
  total_bytes INTEGER NOT NULL,
  reclaimable_bytes INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (job_id, signature),
  FOREIGN KEY (job_id) REFERENCES scan_jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS exact_group_items (
  group_id INTEGER NOT NULL,
  file_id INTEGER NOT NULL,
  is_primary INTEGER NOT NULL DEFAULT 0,
  keep_score REAL,
  reason TEXT,
  PRIMARY KEY (group_id, file_id),
  FOREIGN KEY (group_id) REFERENCES exact_groups(id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

-- Группы similar-дубликатов
CREATE TABLE IF NOT EXISTS similar_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  algorithm TEXT NOT NULL CHECK (algorithm IN ('phash64', 'dhash64', 'hybrid')),
  threshold INTEGER NOT NULL,
  file_count INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (job_id) REFERENCES scan_jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS similar_group_items (
  group_id INTEGER NOT NULL,
  file_id INTEGER NOT NULL,
  distance_to_anchor INTEGER NOT NULL,
  confidence REAL,
  is_primary INTEGER NOT NULL DEFAULT 0,
  keep_score REAL,
  reason TEXT,
  PRIMARY KEY (group_id, file_id),
  FOREIGN KEY (group_id) REFERENCES similar_groups(id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_similar_group_items_distance
  ON similar_group_items(group_id, distance_to_anchor);

-- Решения пользователя на уровне группы/файла
CREATE TABLE IF NOT EXISTS user_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  group_kind TEXT NOT NULL CHECK (group_kind IN ('exact', 'similar')),
  group_id INTEGER NOT NULL,
  file_id INTEGER NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('keep', 'trash', 'delete', 'ignore')),
  note TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(group_kind, group_id, file_id)
);

CREATE INDEX IF NOT EXISTS idx_user_decisions_lookup
  ON user_decisions(group_kind, group_id, decision);

-- Пакет подтвержденных действий (можно откатывать)
CREATE TABLE IF NOT EXISTS action_batches (
  id TEXT PRIMARY KEY,                          -- UUID
  requested_at TEXT NOT NULL DEFAULT (datetime('now')),
  confirmed_at TEXT,
  executed_at TEXT,
  status TEXT NOT NULL CHECK (status IN ('draft', 'confirmed', 'executed', 'partially_failed', 'failed', 'rolled_back')),
  action_type TEXT NOT NULL CHECK (action_type IN ('move_to_trash', 'delete_permanent', 'restore')),
  requested_by TEXT NOT NULL DEFAULT 'local_admin',
  dry_run INTEGER NOT NULL DEFAULT 0,
  summary TEXT
);

CREATE TABLE IF NOT EXISTS action_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  file_id INTEGER NOT NULL,
  source_path TEXT NOT NULL,
  target_path TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending', 'done', 'failed', 'skipped')),
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  executed_at TEXT,
  FOREIGN KEY (batch_id) REFERENCES action_batches(id) ON DELETE CASCADE,
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE RESTRICT,
  UNIQUE(batch_id, file_id)
);

CREATE INDEX IF NOT EXISTS idx_action_items_batch_status ON action_items(batch_id, status);

-- История перемещений для восстановления
CREATE TABLE IF NOT EXISTS file_movements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL,
  batch_id TEXT NOT NULL,
  from_path TEXT NOT NULL,
  to_path TEXT NOT NULL,
  moved_at TEXT NOT NULL DEFAULT (datetime('now')),
  restored_at TEXT,
  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE RESTRICT,
  FOREIGN KEY (batch_id) REFERENCES action_batches(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_file_movements_file_id ON file_movements(file_id);
