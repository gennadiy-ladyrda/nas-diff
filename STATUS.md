# STATUS

Актуально на: `2026-03-13`

## 1. Общий статус проекта
- Текущая стадия: v1 baseline закрыт по backend, UI, QA и ops-документации.
- Продуктовый режим безопасности: `move_to_trash` по умолчанию, `HARD_DELETE_ENABLED=false`.
- Ближайший фокус: проверить на реальном большом каталоге scan после hotfix (`job timeout + rollback`), затем запустить полный UI regression (`vitest + playwright`) в окружении с Node.js/npm.

## 2. Прогресс по backlog
| Task | Статус | Комментарий |
|---|---|---|
| INFRA-01 | done | Выполнен backend scaffold, Docker-окружение, health endpoint и worker startup. |
| DB-01 | done | Реализованы миграции, ORM-модели и репозитории для ключевых сущностей. |
| API-01 | done | Реализованы health и CRUD для `scan_roots` с валидацией путей и API-тестами. |
| API-02 | done | Реализованы API scan jobs + очередь + endpoint выдачи групп/статусов. |
| CORE-01 | done | Реализован файловый сканер с инкрементальной индексацией и `is_present`. |
| CORE-02 | done | Реализована exact-дедупликация и метрика `reclaimable_bytes`. |
| CORE-03 | done | Реализована similar-дедупликация (phash-like, Hamming threshold). |
| DECISION-01 | done | Реализован auto-primary scoring и API сохранения пользовательских решений. |
| ACT-01 | done | Реализованы actions API, action worker executor, rollback через `file_movements` и интеграционные тесты. |
| UI-01 | done | Добавлен frontend dashboard + scan setup с polling статусов, health и обработкой ошибок API. |
| UI-02 | done | Добавлен frontend review groups + action center (decision override, draft/confirm, rollback). |
| QA-01 | done | Добавлены frontend component/e2e smoke tests, backend regression test и единый regression script. |
| OPS-01 | done | Добавлен DSM6 runbook: install/update/backup/restore/troubleshooting и safety правила. |

## 3. Детали выполнения INFRA-01
- Добавлен единый образ backend (`Python 3.11`, `FastAPI`, `RQ`, `Redis client`) для сервисов `api` и `worker`.
- Реализован endpoint `GET /api/v1/health` с проверками SQLite и Redis.
- Реализован запуск worker-процесса через `python -m app.worker` с логами готовности цикла обработки.
- Добавлена централизованная загрузка конфигурации из env (`app/config.py`).
- Согласован `docker-compose.yml`: worker использует тот же image без отдельного `build`.

## 4. Проверки по INFRA-01
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app` -> ok.
- `docker compose config` -> ok.
- `NAS_MOUNT_PATH=... docker compose up -d --build` -> ok (api/worker/redis стартуют).
- `docker compose exec -T api ... /api/v1/health` -> `200`, компоненты `database=ok`, `redis=ok`.
- `docker compose logs worker` -> worker слушает `scan_queue, action_queue`.

## 5. Риски и ограничения
- Хостовый smoke-check через `curl 127.0.0.1:18080` в sandbox нестабилен; health подтвержден изнутри контейнера.
- В рабочем каталоге может оставаться legacy-файл `data/nas_diff.db`; актуальный путь хранения БД перенесен в `~/.nas-diff/data`.

## 6. Следующий практический шаг
- Выполнить `bash scripts/ci/run_s3_regression_suite.sh` в окружении с установленным `node`/`npm` и browser runtime для Playwright.

## 7. Детали выполнения DB-01
- Добавлен DB-layer на `SQLAlchemy 2.x`:
  - `app/db/session.py` для engine/session factory и `PRAGMA foreign_keys=ON`.
  - `app/db/models.py` с ORM-моделями ключевых таблиц (`scan_jobs`, `files`, `exact/similar groups`, `action_batches/items` и связанных сущностей).
- Добавлен migration runner:
  - `app/db/migrations/__init__.py` + миграция `0001_init.sql`.
  - Хранение состояния миграций в `schema_migrations` с checksum-контролем.
  - Защита от destructive SQL по умолчанию (`DB_ALLOW_DESTRUCTIVE_MIGRATIONS=false`).
- Реализованы репозитории:
  - `ScanJobRepository`, `FileRepository`, `GroupRepository`, `ActionRepository`.
- Миграции подключены в startup API и worker.
- Добавлены тесты:
  - интеграционные тесты миграций,
  - unit CRUD-тесты репозиториев.

## 8. Проверки по DB-01
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests` -> ok.
- `sqlite3 :memory: ".read database/schema.sql"` -> ok.
- `docker compose config` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q` (backend) -> `7 passed`.

## 9. Локальный запуск (ops helper)
- Добавлен `justfile` с командами локального профиля:
  - `just up`, `just down`, `just ps`, `just logs`, `just health`, `just config`.
- `.env.local` добавлен в `.gitignore` для защиты локальных параметров от случайного коммита.

## 10. Хранение SQLite в home-каталоге
- Локальный каталог БД перенесен из репозитория в home пользователя:
  - host-путь по умолчанию: `~/.nas-diff/data`;
  - в контейнере используется mount в `/data`.
- В `docker-compose.yml` bind volume переключен на `HOST_DATA_DIR` (с дефолтом на home-каталог).
- В `justfile` добавлено автосоздание каталога `HOST_DATA_DIR` перед запуском.
- Файл `data/nas_diff.db` исключен из состава репозитория, а `data/` добавлен в `.gitignore`.

## 11. Синхронизация архитектурной документации
- Обновлены документы:
  - `docs/architecture.md`;
  - `docs/specification.md`;
  - `docs/database-schema.md`;
  - `docs/blueprint-v1.md`.
- Убрано дублирование статуса выполнения из архитектурных документов.
- Оставлены только операционные изменения:
  - хранение SQLite в `~/.nas-diff/data` через `HOST_DATA_DIR`;
  - локальный запуск через `.env.local` и `justfile`.

## 12. Детали выполнения API-01
- Добавлен API для источников сканирования:
  - `POST /api/v1/scan/roots` (add with canonical path validation);
  - `GET /api/v1/scan/roots` (list);
  - `PATCH /api/v1/scan/roots/{root_id}` (enable/disable);
  - `DELETE /api/v1/scan/roots/{root_id}` (remove).
- Реализована строгая валидация путей:
  - только абсолютные пути;
  - canonical normalization через `posixpath.normpath`;
  - запрет путей вне mount root `/nas`.
- Добавлен репозиторий `ScanRootRepository` с обработкой конфликтов:
  - duplicate path -> `409`;
  - delete при `scan_job_roots` ссылках -> `409`.
- `GET /api/v1/health` расширен компонентом `api` и агрегированием статуса по `api/database/redis`.
- Роутер `scan_roots` подключен в `app/main.py`.

## 13. Проверки по API-01
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests` -> ok.
- `docker compose config` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q` (backend) -> `10 passed`.

## 14. Детали выполнения API-02
- Добавлены endpoint'ы scan jobs:
  - `POST /api/v1/scan/jobs`;
  - `GET /api/v1/scan/jobs/{job_id}`;
  - `GET /api/v1/scan/jobs/{job_id}/groups?kind=exact|similar`.
- Добавлена интеграция с очередью:
  - `ScanQueueClient` + `RQScanQueueClient`;
  - enqueue в `scan_queue`;
  - worker task `app.workers.scan_worker.process_scan_job`.
- Добавлена идемпотентность создания job через `idempotency_key`.

## 15. Детали выполнения CORE-01 / CORE-02 / CORE-03
- CORE-01:
  - модуль `core/scanner.py` для обхода scan roots;
  - инкрементальная проверка изменений по `size/mtime/inode/dev`;
  - обновление `files`, `file_hashes`, `is_present`, `last_seen_job_id`.
- CORE-02:
  - потоковый full-hash в `core/hasher_exact.py` (`blake3` при наличии, иначе fallback);
  - построение exact-групп в `core/dedup_exact.py` по `blake3_full`;
  - расчет `reclaimable_bytes`.
- CORE-03:
  - вычисление `dhash64/phash64` в `core/hasher_similar.py`;
  - Hamming-distance и построение connected components в `core/dedup_similar.py`;
  - сохранение `similar_groups` + `distance_to_anchor/confidence`.
- Добавлен orchestration-слой `services/scan_orchestrator.py`, объединяющий scan + dedup + статус job.

## 16. Детали выполнения DECISION-01
- Добавлен `core/decision_engine.py`:
  - scoring по правилам (`resolution`, `size`, `EXIF`, `mtime`);
  - инвариант ровно одного `is_primary` на группу.
- Добавлен `services/decision_service.py`:
  - сохранение решений в `user_decisions`;
  - ручной override primary при решении `keep`.
- Добавлен API:
  - `POST /api/v1/groups/{group_kind}/{group_id}/decision`;
  - `GET /api/v1/groups/{group_kind}/{group_id}`.

## 17. Проверки по API-02 / CORE-01 / CORE-02 / CORE-03 / DECISION-01
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests` -> ok.
- `docker compose config` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q` (backend) -> `18 passed`.

## 18. Детали выполнения ACT-01
- Добавлен API `actions`:
  - `POST /api/v1/actions/batches` (создание draft batch);
  - `GET /api/v1/actions/batches/{batch_id}` (статус и пофайловые результаты);
  - `POST /api/v1/actions/batches/{batch_id}/confirm` (подтверждение и enqueue в `action_queue`);
  - `POST /api/v1/actions/batches/{batch_id}/rollback` (создание restore-batch из `file_movements`).
- Добавлен `ActionService`:
  - валидация переходов `draft -> confirmed -> executed|partially_failed|failed`;
  - исполнение `move_to_trash`, `delete_permanent`, `restore` с пофайловыми ошибками без silent-fail;
  - блокировка `delete_permanent` при `HARD_DELETE_ENABLED=false`;
  - auto-mark исходного `move_to_trash` batch как `rolled_back` после полного восстановления.
- Добавлен worker executor:
  - `app.workers.action_worker.process_action_batch`;
  - очередь `ActionQueueClient` / `RQActionQueueClient` c enqueue в `action_queue`.
- Расширен DB-layer:
  - ORM-модель `FileMovement`;
  - методы репозитория для логирования перемещений и фиксации `restored_at`.
- Добавлены интеграционные тесты `ACT-01`:
  - happy path `move_to_trash -> execute -> rollback`;
  - блок hard delete при выключенном флаге;
  - failure path с проверкой `action_items.error_message`.

## 19. Проверки по ACT-01
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests` -> ok.
- `docker compose config` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q` (backend) -> `21 passed`.

## 20. Детали выполнения UI-01 / UI-02
- Добавлен новый frontend-модуль (`React + Vite`) в `frontend/`:
  - `src/pages/DashboardPage.jsx`: health, scan roots, запуск scan jobs, polling статуса и метрик.
  - `src/pages/ReviewPage.jsx`: список exact/similar групп, просмотр деталей группы, сохранение decisions.
  - Action Center в UI: создание draft batch, confirm batch, мониторинг item-статусов, rollback.
- Добавлен API-клиент `frontend/src/api/client.js` с контрактами для `health/scan/groups/actions`.
- Добавлены UI-компоненты (`Panel`, `StatusBadge`, `ErrorBanner`) и единый стиль `src/styles/global.css`.
- Реализовано хранение последних `job_id` в `localStorage` и навигация `Dashboard <-> Review`.
- Интеграция в инфраструктуру:
  - добавлен сервис `frontend` в `docker-compose.yml`;
  - добавлен `frontend/Dockerfile` и `frontend/nginx.conf` (SPA + proxy `/api` -> `api:8080`);
  - обновлены `.env.example` и `.env.local` (`FRONTEND_PORT`).

## 21. Детали выполнения QA-01
- Добавлены frontend component tests:
  - `frontend/tests/component/dashboard-page.test.jsx`;
  - `frontend/tests/component/review-page.test.jsx`.
- Добавлены frontend e2e smoke tests (mock API, Playwright):
  - `frontend/tests/e2e/scan-launch.spec.js`;
  - `frontend/tests/e2e/review-actions.spec.js`.
- Добавлен backend regression-тест полного workflow:
  - `backend/tests/api/test_qa_01_regression.py`.
- Добавлен единый regression runner:
  - `scripts/ci/run_s3_regression_suite.sh`.

## 22. Детали выполнения OPS-01
- Добавлен эксплуатационный runbook `docs/ops/dsm6-runbook.md`:
  - install/start/stop/update;
  - backup/restore для SQLite и Redis AOF;
  - troubleshooting по `database is locked`, `redis down`, `permission denied`;
  - safety policy по `move_to_trash` и `delete_permanent`.

## 23. Проверки по UI-01 / UI-02 / QA-01 / OPS-01
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `24 passed`.
- `docker compose config` -> ok (включая новый сервис `frontend`).
- Ограничение текущего sandbox: `npm` отсутствует (`npm: command not found`), поэтому `vitest/playwright` в этом окружении не запускались.

## 24. Hotfix scan timeout + failed status persistence
- В конфигурацию добавлен параметр `SCAN_JOB_TIMEOUT_SECONDS` (default `7200`):
  - `backend/app/config.py`;
  - `.env.example`, `.env.local`;
  - `docker-compose.yml`.
- Для scan queue задан явный RQ timeout из конфига:
  - `backend/app/workers/queue.py` (`job_timeout` при enqueue scan job).
- Исправлена обработка падения scan job в оркестраторе:
  - `backend/app/services/scan_orchestrator.py` теперь делает `session.rollback()` перед `update_status(..., failed, ...)`.
  - Это устраняет зависание job в `running` после transaction errors / timeout.
- Снижена нагрузка на SQLite во время сканирования:
  - `backend/app/core/scanner.py` переведен на batched commits (`_COMMIT_BATCH_SIZE=250`).
  - `backend/app/db/repositories/files.py` и `file_hashes.py` поддерживают `autocommit=False` для batched режима.
- Добавлены регрессионные тесты:
  - `backend/tests/core/test_scan_orchestrator_failures.py` (проверка failed-status после flush error);
  - `backend/tests/api/test_worker_queue_config.py` (проверка применения timeout в queue client).
