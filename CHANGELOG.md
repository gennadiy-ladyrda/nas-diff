# Changelog

Все значимые изменения в проекте `nas-diff` фиксируются в этом файле.

Формат основан на принципах Keep a Changelog.

## [Unreleased]

## [2026-03-13] API-02 + CORE-01/02/03 + DECISION-01 - Scan pipeline, dedup и решения пользователя

### Added
- API scan jobs:
  - `POST /api/v1/scan/jobs`;
  - `GET /api/v1/scan/jobs/{job_id}`;
  - `GET /api/v1/scan/jobs/{job_id}/groups`.
- API groups/decisions:
  - `GET /api/v1/groups/{group_kind}/{group_id}`;
  - `POST /api/v1/groups/{group_kind}/{group_id}/decision`.
- Queue + worker scan pipeline:
  - `ScanQueueClient` / `RQScanQueueClient`;
  - `app.workers.scan_worker.process_scan_job`.
- Core модули:
  - `scanner.py` (инкрементальный обход и индексация);
  - `hasher_exact.py`, `hasher_similar.py`;
  - `dedup_exact.py`, `dedup_similar.py`;
  - `decision_engine.py`.
- Service layer:
  - `scan_orchestrator.py`;
  - `decision_service.py`.
- DB repositories:
  - `file_hashes.py`;
  - `decisions.py`.
- Тесты:
  - `backend/tests/api/test_api_02_scan_jobs.py`;
  - `backend/tests/api/test_decision_01_groups.py`;
  - `backend/tests/core/test_core_pipeline.py`;
  - `backend/tests/core/conftest.py`.

### Changed
- `backend/app/main.py`: подключены роуты scan и groups.
- `backend/app/db/models.py`: добавлены ORM-модели `FileHash`, `UserDecision`.
- `backend/app/db/repositories/scan_jobs.py`: добавлены операции связки job <-> roots.
- `backend/app/db/repositories/groups.py`: раздельная очистка exact/similar групп.
- `backend/tests/api/conftest.py`: добавлен in-memory queue override для интеграционных API-тестов.
- `backend/tests/db/test_repositories.py`: добавлены тесты `FileHashRepository` и `UserDecisionRepository`.

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests`.
- `docker compose config`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q` (backend) -> `18 passed`.

## [2026-03-13] API-01 - Health и управление источниками сканирования

### Added
- Новый API-роутер `scan_roots`:
  - `POST /api/v1/scan/roots`;
  - `GET /api/v1/scan/roots`;
  - `PATCH /api/v1/scan/roots/{root_id}`;
  - `DELETE /api/v1/scan/roots/{root_id}`.
- Новый DB-репозиторий `ScanRootRepository`:
  - create/list/update enabled/delete;
  - доменные ошибки `ScanRootAlreadyExistsError`, `ScanRootInUseError`.
- API-тесты:
  - `backend/tests/api/conftest.py`;
  - `backend/tests/api/test_api_01_scan_roots.py`.

### Changed
- `GET /api/v1/health` дополнен компонентом `api` и итоговым статусом по всем зависимостям (`api`, `database`, `redis`).
- Добавлена строгая валидация path для scan roots:
  - только абсолютные пути;
  - canonical normalization (`posixpath.normpath`);
  - запрет путей вне `/nas`.
- Роутер `scan_roots` подключен в `backend/app/main.py`.
- `backend/app/db/session.py`: `get_db_session` приведен к dependency-friendly сигнатуре без входных параметров.

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests`.
- `docker compose config`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q` (backend) -> `10 passed`.

## [2026-03-13] DOCS-ARCH-01 - Синхронизация архитектурных документов по операционным решениям

### Changed
- `docs/architecture.md`: добавлены и уточнены операционные соглашения по хранению SQLite в `~/.nas-diff/data` (`HOST_DATA_DIR`) и локальному запуску через `.env.local` + `justfile`.
- `docs/specification.md`: уточнен конфигурационный раздел (`HOST_DATA_DIR`, `APP_DATA_DIR`, `DB_ALLOW_DESTRUCTIVE_MIGRATIONS`) и добавлены правила локального запуска через `justfile`.
- `docs/database-schema.md`: зафиксировано размещение SQLite на хосте через `HOST_DATA_DIR` и исключение `data/` из git.
- `docs/blueprint-v1.md`: закреплены операционные решения по каталогу данных в home пользователя и локальному профилю запуска.
- Из архитектурных документов убрано дублирование статуса выполнения, оставлены только актуальные архитектурные/операционные договоренности.

### Validation
- Проверка документов на консистентность терминов и параметров:
  - `HOST_DATA_DIR`, `APP_DATA_DIR`, `.env.local`, `justfile`.

## [2026-03-13] OPS-LOCAL-02 - Хранение данных в home-каталоге пользователя

### Added
- Поддержка host-каталога данных `HOST_DATA_DIR` для docker-compose (рекомендуемый путь: `~/.nas-diff/data`).
- Автосоздание каталога `HOST_DATA_DIR` в `just init-local` перед `up/config`.

### Changed
- `docker-compose.yml`: bind mount `./data:/data` заменен на `${HOST_DATA_DIR:-${HOME}/.nas-diff/data}:/data`.
- `backend/app/config.py`: дефолтный путь БД вне Docker перенесен в home пользователя (`~/.nas-diff/data/nas_diff.db`).
- `.env.example` и `.env.local`: добавлен/заполнен `HOST_DATA_DIR`.
- `.gitignore`: добавлен `data/`; `data/nas_diff.db` удален из индекса git.

### Validation
- `just --list`.
- `just config` (резолв bind mount в `/Users/gena/.nas-diff/data`).
- `just up`.
- `just health` (`status=ok`, `database=ok`, `redis=ok`).
- Проверка на хосте: создан каталог `/Users/gena/.nas-diff/data` и файл `nas_diff.db`.

## [2026-03-13] OPS-LOCAL-01 - Локальный профиль запуска через just

### Added
- `justfile` с командами локального управления compose:
  - `up`, `down`, `ps`, `logs`, `health`, `config`, `restart`.
- Автоподготовка mock-директорий NAS в `just init-local`.

### Changed
- `.gitignore`: добавлен `.env.local`.

### Validation
- `just --list` -> рецепты обнаружены корректно.
- `just config` -> compose-конфиг успешно рендерится с `.env.local`.

## [2026-03-13] DB-01 - Модель данных, миграции и репозитории

### Added
- DB-layer на `SQLAlchemy`:
  - `backend/app/db/session.py` (engine/session factory, `PRAGMA foreign_keys=ON`);
  - `backend/app/db/models.py` (ORM-модели ключевых таблиц);
  - `backend/app/db/repositories/`:
    - `scan_jobs.py`,
    - `files.py`,
    - `groups.py`,
    - `actions.py`.
- Migration runner:
  - `backend/app/db/migrations/__init__.py`;
  - `backend/app/db/migrations/sql/0001_init.sql` (init-схема, синхронизирована с `database/schema.sql`);
  - таблица `schema_migrations` с checksum-контролем.
- Тесты DB-слоя:
  - `backend/tests/db/test_migrations.py`;
  - `backend/tests/db/test_repositories.py`;
  - `backend/tests/db/helpers.py`;
  - `backend/pytest.ini`.

### Changed
- `backend/app/main.py` и `backend/app/worker.py`: авто-применение миграций на startup.
- `backend/app/config.py`, `.env.example`, `docker-compose.yml`: добавлен флаг `DB_ALLOW_DESTRUCTIVE_MIGRATIONS` (по умолчанию `false`).
- `backend/requirements.txt`: добавлен `sqlalchemy==2.0.37`.
- `backend/app/db/__init__.py`: экспорт DB API (models/session/migrations).

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests`.
- `sqlite3 :memory: ".read database/schema.sql"`.
- `docker compose config`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q` в `backend/` -> `7 passed`.

## [2026-03-13] INFRA-01 - Базовый каркас backend/worker и контейнеров

### Added
- `backend/` scaffold:
  - `Dockerfile`, `requirements.txt`.
  - `app/main.py` с FastAPI-приложением.
  - `app/api/routes_health.py` c endpoint `GET /api/v1/health`.
  - `app/worker.py` и `app/workers/queue.py` для запуска RQ worker.
  - `app/config.py` для чтения runtime-настроек из env.
  - базовые package-модули `app/api`, `app/core`, `app/db`, `app/services`, `app/workers`.
- Новые env-параметры в `.env.example`:
  - `APP_NAME`, `APP_VERSION`, `APP_ENV`, `LOG_LEVEL`.
  - `DATABASE_URL`, `REDIS_URL`, `WORKER_QUEUES`.

### Changed
- `docker-compose.yml`:
  - сервис `worker` переведен на использование уже собранного `nas-diff-api:0.1.0` без собственного `build`;
  - устранен конфликт параллельной сборки одного и того же image для `api` и `worker`.

### Validation
- Выполнены проверки:
  - `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app`.
  - `docker compose config`.
  - `docker compose up -d --build` (smoke).
  - Проверка `GET /api/v1/health` (HTTP 200) из контейнера `api`.
  - Проверка логов `worker` на успешный startup и подписку на очереди.

### Notes
- В ходе smoke-check создан локальный `data/nas_diff.db`.
- Для `docker-compose.yml` наблюдается warning об устаревшем поле `version`.
