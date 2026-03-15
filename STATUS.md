# STATUS

Актуально на: `2026-03-15`

## 1. Общий статус проекта
- Текущая стадия: v1 baseline закрыт по backend, UI, QA и ops-документации.
- Продуктовый режим безопасности: `move_to_trash` по умолчанию, `HARD_DELETE_ENABLED=false`.
- Ближайший фокус: финальный smoke для `Simple Scan` primary flow, затем release freeze v1.

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
| API-03 | done | Реализованы `GET /scan/jobs` (filters/pagination/sort) и `DELETE /scan/jobs/{job_id}` с проверкой зависимостей. |
| UI-03 | done | Dashboard переработан в двухколоночный layout, добавлен delete roots с confirm-step и понятными error-messages. |
| UI-04 | done | Добавлены jobs table (filters/sort/pagination), detail panel по клику и display-name `SCAN-<MODE>-<SEQ>`. |
| ACT-02 | done | Реализованы bulk scopes (`selected/all_in_group/all_filtered`), preview endpoint и staged confirm для destructive flow. |
| QA-02 | done | Добавлены регрессионные сценарии roots/jobs/bulk UX и обновлен единый regression runner для локальной воспроизводимости. |
| UX-SKETCH-01 | in_review | Добавлен эскиз двух экранов dashboard (`advanced/simple`) и массовый UX выбора групп/решений в Review. |
| UI-05 | done | `Simple Scan` автоподставляет path/mode из последнего processed job с fallback в localStorage/default. |
| ACT-03 | done | Добавлен simple action flow `preview -> draft -> confirm` по всем distinct non-primary файлам последнего job. |
| UI-06 | done | Стартовый маршрут переключен на `Simple Scan`, `Advanced`/`Review` перенесены в hamburger-menu. |

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
- Прогнать полный frontend smoke (`vitest`/browser/e2e) в окружении с `node/npm` и зафиксировать release-candidate UX.

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

## 25. Детали выполнения API-03
- Добавлены новые endpoint'ы API scan jobs:
  - `GET /api/v1/scan/jobs` с фильтрами `status/mode`, пагинацией (`page/page_size`) и сортировкой по `requested_at`.
  - `DELETE /api/v1/scan/jobs/{job_id}` для удаления метаданных job без воздействия на NAS-файлы.
- Реализована safe policy удаления:
  - запрет удаления jobs в статусах `queued`/`running`;
  - проверка зависимостей перед удалением (`exact_groups`, `similar_groups`, `action_items`);
  - при зависимостях возвращается `409` с понятной причиной конфликта.
- Расширен `ScanJobRepository`:
  - `list_jobs(...)` для UI-каталога jobs;
  - `count_delete_dependencies(job_id)` для валидации cleanup;
  - `delete(job_id)` для удаления метаданных.
- Добавлены тесты:
  - API: `backend/tests/api/test_api_03_scan_jobs_catalog.py`;
  - DB repository: расширение `backend/tests/db/test_repositories.py`.

## 26. Проверки по API-03
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_api_02_scan_jobs.py backend/tests/api/test_api_03_scan_jobs_catalog.py backend/tests/db/test_repositories.py` -> `14 passed`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `30 passed`.
- `docker compose config` -> ok.

## 27. Детали выполнения UI-03
- Dashboard layout обновлен до операционного вида:
  - фиксированная левая колонка `System Health`;
  - основная правая колонка для `Scan Setup`, `Scan Roots Registry` и `Scan Jobs Journal`.
- Реализовано удаление scan roots из UI:
  - кнопка `Delete` для каждого root;
  - обязательный `confirm-step`;
  - человекочитаемые ошибки для `409/422` без потери контекста.
- Реестр roots расширен:
  - быстрый toggle `enabled`;
  - сохранен безопасный инвариант (удаляются только метаданные).

## 28. Детали выполнения UI-04
- Добавлена таблица jobs:
  - колонки `display name`, `mode/status`, `requested/finished`, files/groups counters, reclaimable bytes;
  - фильтры `status/mode`, сортировка `newest|oldest`, пагинация.
- Добавлена детализация job по клику:
  - detail panel с метриками, roots, error_message;
  - сохранен ручной вход по `job_id` (`Open Job By ID`).
- Добавлен UI-нейминг jobs:
  - формат `SCAN-<MODE>-<SEQ>` + timestamp;
  - технический `job_id` всегда отображается отдельно.
- Добавлено удаление job-метаданных из UI:
  - action `Delete` в таблице и detail panel;
  - confirm-step и обработка конфликтов safe-delete.

## 29. Проверки по UI-03 / UI-04
- `docker compose config` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `30 passed` (проверка на отсутствие backend-регрессий после UI-интеграции).
- Ограничение окружения: `npm` отсутствует (`npm: command not found`), поэтому `vitest` и `playwright` в текущем sandbox не запускались.

## 30. Hotfix UI polling + stale running job cleanup
- Исправлен polling в dashboard jobs journal:
  - удален full-reload списка jobs из автоматического polling-цикла;
  - polling обновляет только runtime-поля активных (`queued/running`) jobs;
  - в таблицу добавлена колонка `Progress` с динамическим progress-bar, чтобы визуально обновлялся только прогресс по строкам.
- Добавлен безопасный путь удаления stale `running/queued` jobs:
  - `DELETE /api/v1/scan/jobs/{job_id}` поддерживает `allow_stale_running=true`;
  - удаление активного job разрешается только при явном флаге и если job стал stale (старше `SCAN_JOB_TIMEOUT_SECONDS`);
  - для свежих активных jobs сохраняется блокировка `409`.
- UI удаления job обновлен:
  - при `409` для active job появляется второй confirm-step для stale cleanup;
  - повторный delete отправляется с `allow_stale_running=true`.

## 31. Проверки по hotfix UI polling + stale cleanup
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests frontend/src` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_api_03_scan_jobs_catalog.py` -> `7 passed`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `32 passed`.
- `docker compose config` -> ok.
- Ограничение окружения: `node/npm` отсутствуют, поэтому frontend `vitest/playwright` не запускались в текущем sandbox.

## 32. Детали выполнения ACT-02
- Backend:
  - добавлен endpoint `POST /api/v1/actions/batches/preview`;
  - в `ActionService` добавлен расчет preview последствий (`files_count`, `total_bytes`, `estimated_reclaimable_bytes`) с валидацией action/file_ids;
  - для `restore` preview проверяет наличие unrestored movement и не допускает silent-fail.
- Frontend (`ReviewPage`):
  - добавлены bulk scopes: `selected`, `all_in_group`, `all_filtered`;
  - добавлен обязательный шаг `Preview Impact` перед созданием draft batch;
  - создание draft batch блокируется до получения preview;
  - для `delete_permanent` добавлен усиленный staged-confirm (checkbox + отдельный confirm при подтверждении batch);
  - execution report расширен метриками `pending/done/failed/skipped`;
  - rollback оставлен быстрым действием для `move_to_trash` (`executed/partially_failed`).
- Tests:
  - backend API tests расширены сценариями preview;
  - frontend component/e2e тесты обновлены под новый preview-first flow и `all_filtered` scope.

## 33. Проверки по ACT-02
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests frontend/src` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_act_01_actions.py backend/tests/api/test_qa_01_regression.py` -> `6 passed`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `34 passed`.
- `docker compose config` -> ok.
- Ограничение окружения: `node/npm` отсутствуют, поэтому frontend `vitest/playwright` не запускались в текущем sandbox.

## 34. Детали выполнения QA-02
- Backend regression:
  - добавлен новый сквозной тест `backend/tests/api/test_qa_02_regression.py`:
    - root delete conflict (`409`) для root, связанного с job;
    - scan jobs list/filter сценарий после выполнения scan;
    - bulk preview (`/actions/batches/preview`) -> create -> confirm -> execute -> rollback.
- Frontend regression:
  - `frontend/tests/component/review-page.test.jsx`:
    - добавлен сценарий rollback после executed `move_to_trash` batch;
    - подтвержден `all_filtered` scope и preview-first flow.
  - `frontend/tests/e2e/review-actions.spec.js`:
    - smoke расширен до полного цикла `preview -> draft -> confirm -> execute -> rollback`.
- CI regression script:
  - `scripts/ci/run_s3_regression_suite.sh` теперь:
    - автоматически подбирает python интерпретатор с доступным `pytest`;
    - поддерживает `SKIP_FRONTEND=1` для локального backend-only прогона;
    - дает явную ошибку, если `npm` недоступен.

## 35. Проверки по QA-02
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests frontend/src` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_qa_02_regression.py backend/tests/api/test_api_01_scan_roots.py backend/tests/api/test_api_03_scan_jobs_catalog.py backend/tests/api/test_act_01_actions.py` -> `16 passed`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `35 passed`.
- `docker compose config` -> ok.
- `SKIP_FRONTEND=1 SKIP_PLAYWRIGHT=1 bash scripts/ci/run_s3_regression_suite.sh` -> ok (backend-only режим).
- Ограничение окружения: `npm` отсутствует, поэтому frontend `vitest/playwright` в этом sandbox не запускались.

## 36. Детали выполнения UX-SKETCH-01
- Dashboard разделен на два экрана:
  - `Advanced` (`/`) сохраняет текущий расширенный dashboard.
  - `Simple Scan` (`/scan`) показывает только:
    - ручной ввод каталога сканирования,
    - выбор режима (`exact/similar/both`),
    - запуск scan,
    - компактный progress-bar.
- Для `Simple Scan` добавлен безопасный flow запуска:
  - путь резолвится в `scan_root` (используется существующий либо создается новый metadata-root),
  - затем запускается scan job без удаления/перемещения файлов.
- `Review & Actions` эскизно расширен под массовые операции:
  - явные checkbox у групп (`select for batch`);
  - быстрые команды `Select All Groups` / `Clear Selection`;
  - новый bulk scope: `selected_groups`;
  - новый блок `Batch decision for groups` для массового решения по всем выбранным группам;
  - новый блок `Apply one decision to selected files` в `Group Details` для назначения одного решения множеству выбранных файлов.
- По логам запущенного приложения подтверждено, что при открытом `Review` идет постоянный polling:
  - `GET /api/v1/scan/jobs/{job_id}/groups?...` каждые ~5 секунд.
  - Это объясняет ощущение постоянного обновления и стало входом для UX-эскиза более явного bulk-flow.

## 37. Проверки по UX-SKETCH-01
- `docker compose config` -> ok.
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests frontend/src` -> ok.
- Проверены runtime-логи:
  - `docker compose logs --tail=120 frontend`
  - `docker compose logs --tail=120 api`
  - наблюдается регулярный polling `groups` endpoint из `Review`.
- Ограничение окружения: `node/npm` отсутствуют в host sandbox, поэтому `vitest`/`playwright` локально не запускались.

## 38. Детали планирования TASKS-03 (UI-05 / ACT-03 / UI-06)
- Добавлены новые task-brief файлы:
  - `tasks/UI-05.md` — автоподстановка последнего `path/mode` в `Simple Scan`.
  - `tasks/ACT-03.md` — единое action-действие по всем релевантным файлам последнего job из `Simple Scan`.
  - `tasks/UI-06.md` — hamburger-навигация и default route на `Simple Scan`.
- Обновлен `tasks/README.md`:
  - добавлены пункты `19..21`,
  - новые файлы включены в секцию `Файлы задач`.
- Реализация задач не выполнялась (только описание и постановка).

## 39. Детали выполнения UI-05 / ACT-03 / UI-06
- `Simple Scan` обновлен до primary flow:
  - при загрузке вызывает `GET /api/v1/scan/jobs/latest/processed`;
  - подставляет `Directory path` и `Scan mode` из последнего обработанного job;
  - при отсутствии processed history использует `localStorage` fallback или дефолт `/nas/photo` + `both`;
  - после успешного запуска scan обновляет локально сохраненные значения.
- Для массового действия в `Simple Scan` добавлен backend-driven flow:
  - `POST /api/v1/actions/jobs/{job_id}/preview`;
  - `POST /api/v1/actions/jobs/{job_id}/batches`;
  - policy: в batch попадают все distinct `non-primary` файлы exact/similar групп указанного job.
- Навигация приложения переработана:
  - маршрут `/` теперь открывает `Simple Scan`;
  - `Advanced` перенесен на `/advanced`;
  - `/scan` оставлен как alias на `/`;
  - `Advanced` и `Review & Actions` доступны через hamburger-меню с close по outside-click и `Esc`.
- Добавлены тесты:
  - backend API для latest processed job и job-scoped action aggregation;
  - frontend component tests для `Simple Scan` defaults/action flow;
  - frontend component test для hamburger-navigation и default routing.

## 40. Проверки по UI-05 / ACT-03 / UI-06
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_act_01_actions.py backend/tests/api/test_api_03_scan_jobs_catalog.py` -> `15 passed`.
- Ограничение текущего sandbox: `npm` отсутствует (`npm: command not found`), поэтому `vitest`/`playwright` локально не запускались.

## 41. Hotfix latest-job preview zero-state
- Исправлен `Simple Scan -> Preview Impact` для latest processed job без actionable duplicate-файлов:
  - backend `POST /api/v1/actions/jobs/{job_id}/preview` теперь возвращает `200` с нулевыми `files_count/bytes`, а не `422`;
  - frontend показывает zero-state сообщение и блокирует `Create Draft Batch (0)`.
- Добавлены проверки:
  - backend API test на zero-preview для пустого job;
  - frontend component test на zero-state preview без error-banner.

## 42. Проверки по hotfix latest-job preview zero-state
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests` -> ok.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_act_01_actions.py` -> `8 passed`.
- Ограничение текущего sandbox: `npm` отсутствует (`npm: command not found`), поэтому frontend component tests локально не запускались.
