# Changelog

Все значимые изменения в проекте `nas-diff` фиксируются в этом файле.

Формат основан на принципах Keep a Changelog.

## [Unreleased]

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
