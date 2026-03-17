# Changelog

Все значимые изменения в проекте `nas-diff` фиксируются в этом файле.

Формат основан на принципах Keep a Changelog.

## [Unreleased]

### Added
- Новый task brief:
  - `tasks/OPS-02.md` — перевод поставки `nas-diff` в формат штатного Synology DSM6 приложения (`.spk`) с запуском из стандартного UI.
- Новый ADR/tech note:
  - `docs/ops/dsm6-package-adr.md` — решения по DSM6 package toolchain, lifecycle scripts и модели запуска контейнерного стека из package runtime.
- Новый layout-документ:
  - `docs/ops/dsm6-package-layout.md` — структура `package/synology-dsm6/`, карта `.spk`-артефактов и границы persistent/immutable данных.
- Новый skeleton package tree:
  - `package/synology-dsm6/` с каталогами `SynoBuildConf`, `assets`, `conf`, `scripts`, `payload`, `payload/ui`, `payload/runtime`, `payload/images`, `payload/port_conf`.
- Initial DSM6 build scaffold:
  - `package/synology-dsm6/INFO.sh`
  - `package/synology-dsm6/SynoBuildConf/depends`
  - `package/synology-dsm6/SynoBuildConf/build`
  - `package/synology-dsm6/SynoBuildConf/install`
  - `scripts/build/build_synology_spk.sh`
  - `just` targets `spk-stage` and `spk-build`
- Package runtime payload scaffold:
  - `payload/runtime/compose/docker-compose.package.yml`
  - `payload/runtime/env/nas-diff.env.template`
  - `payload/runtime/scripts/common.sh`
  - `payload/runtime/scripts/render-runtime-env.sh`
  - `payload/runtime/scripts/render-ui-config.sh`
  - `payload/runtime/scripts/runtime-preflight.sh`
  - `payload/runtime/scripts/docker-load-images.sh`
  - `payload/ui/config`
  - `conf/resource`
  - `payload/port_conf/nas-diff.sc`
- Generated package icons with `DIFF` branding:
  - `scripts/build/generate_synology_icons.py`
  - refreshed `PACKAGE_ICON.PNG`, `PACKAGE_ICON_256.PNG`
  - added launcher icons `payload/ui/images/diff_16.png`, `diff_32.png`, `diff_64.png`
- Bundled image archive pipeline:
  - `scripts/build/bundle_synology_images.sh`
  - `just` targets `spk-images` и `spk-stage-images`
  - generated `payload/images/manifest.env`
- Toolkit validation/build handoff:
  - `scripts/build/check_synology_toolkit.sh`
  - `just` targets `spk-check` и `spk-build-images`
  - `docs/ops/dsm6-runbook.md` расширен package build flow для `PkgCreate.py`
- Dockerized Toolkit wrapper and manual packager:
  - `scripts/build/build_synology_spk_in_docker.sh`
  - `scripts/build/docker/synology-toolkit-builder.Dockerfile`
  - `scripts/build/docker/toolkit-entrypoint.sh`
  - `scripts/build/build_synology_spk_manual.sh`
  - `scripts/build/pack_synology_archive.py`
  - `just` targets `spk-build-docker` и `spk-build-manual`
- Первый реальный `.spk` build artifact:
  - `artifacts/synology-spk/nas-diff-x64-0.1.0-0008.spk`
- Offline execution handoff:
  - `docs/ops/dsm6-package-build-handoff.md` с командами для build host и DSM host без необходимости возвращаться в чат
- Runtime wrapper and DSM lifecycle scaffold:
  - `payload/runtime/env/package.conf.example`
  - `payload/runtime/scripts/start-stack.sh`
  - `payload/runtime/scripts/stop-stack.sh`
  - `payload/runtime/scripts/status-stack.sh`
  - `scripts/preinst`, `postinst`, `preupgrade`, `postupgrade`, `preuninst`, `postuninst`, `start-stop-status`

### Changed
- Hotfix latest-job preview zero-state:
  - `POST /api/v1/actions/jobs/{job_id}/preview` теперь возвращает `200` с нулевым preview, если в job нет actionable `non-primary` duplicate-файлов;
  - `Simple Scan` показывает zero-state вместо error-banner и блокирует создание draft batch при `files_count=0`.
- `tasks/OPS-02.md`:
  - добавлена реализационная декомпозиция `OPS-02.1`..`OPS-02.9`;
  - зафиксирован рекомендуемый стартовый путь: repository-managed `.spk` toolchain и shell lifecycle-скрипты DSM6 как управляющий слой над текущим контейнерным стеком.
- `tasks/README.md`:
  - добавлен backlog-пункт `22. OPS-02`;
  - обновлен список файлов задач.
- `STATUS.md`:
  - `OPS-02` переведен в `in_progress`;
  - зафиксировано закрытие подзадачи `OPS-02.1` через ADR;
  - ближайший фокус переключен на `OPS-02.3`.
- `docs/ops/dsm6-package-adr.md` и `docs/ops/dsm6-package-layout.md`:
  - persistent/runtime paths переведены на стандартные DSM6 package paths `/var/packages/nas-diff/{etc,var,tmp}`.
- `tasks/OPS-02.md`:
  - статус `OPS-02.3` расширен ссылками на runtime payload и icon generator.
- `tasks/OPS-02.md`:
  - `OPS-02.4` и `OPS-02.5` переведены в `in_progress` с привязкой к runtime-wrapper и package scripts scaffold.
- `tasks/OPS-02.md`, `STATUS.md`, `docs/ops/dsm6-runbook.md`, `docs/ops/dsm6-package-build-handoff.md`:
  - `OPS-02.3` переведен в `done`;
  - зафиксирован быстрый рабочий build path `just spk-build-manual`;
  - после уточнения целевой NAS package target переведен с DSM 6.2 на DSM 6.1.4-15217 Update 1 (`DS3615xs-j`, `docker-compose 1.28.5`);
  - следующий практический шаг переключен на DSM 6.1.4 smoke install/start/status/stop на уже собранном `.spk`.
- `scripts/build/build_synology_spk_manual.sh`:
  - упаковка `.spk` и `package.tgz` переведена с macOS `bsdtar/pax` на GNU tar compatible writer через `pack_synology_archive.py`;
  - это устраняет rejection `Неверный формат файла` в DSM Package Center для локально собранного артефакта.
- `package/synology-dsm6/INFO.sh`, `package/synology-dsm6/SynoBuildConf/depends`, build wrappers:
  - минимальная поддерживаемая прошивка понижена до `DSM 6.1-15217`;
  - toolkit defaults переведены на `DSM 6.1 / bromolow`;
  - package version bumped до `0.1.0-0006`, чтобы отделить DSM 6.1 таргет с `docker-compose 1.28`-compatible image references от предыдущих сборок.
- `package/synology-dsm6/conf/resource`:
  - удален из DSM 6.1 package target;
  - официальный Synology `resource` worker требует DSM `6.2-5941+`, поэтому на DSM 6.1 этот файл нельзя включать в пакет.
- `render-runtime-env.sh` и `common.sh`:
  - render step теперь создает `target/runtime/env/nas-diff.env`, который требуется `docker-compose.package.yml`;
  - package config создается и загружается до рендера env, чтобы первый старт не зависел от позднего `run_compose`.
- `docker-compose.package.yml`:
  - удалены nested variable expansions в `image:` полях;
  - это устраняет ошибку `invalid reference format` на `docker-compose 1.28.5` в DSM 6.1.
- `package/synology-dsm6/payload/images/README.md`:
  - задокументированы archive names, manifest и правило не коммитить build artifacts.
- `scripts/build/bundle_synology_images.sh`, `scripts/build/build_synology_spk.sh`, `scripts/build/build_synology_spk_manual.sh`, `justfile`:
  - image bundling теперь по умолчанию таргетирует `linux/amd64` и валидирует фактическую архитектуру образов перед `docker save`;
  - package version bumped до `0.1.0-0008`, чтобы отделить `x86_64`-совместимую пересборку от прежнего артефакта, в который попали образы неверной архитектуры.
- `package/synology-dsm6/payload/runtime/scripts/start-stack.sh`:
  - старт контейнерного стека переведен на `docker-compose up -d --force-recreate --remove-orphans`, чтобы после package update DSM гарантированно пересоздавал контейнеры из новых image archives, а не пытался запускать старые wrong-arch экземпляры.
- `docs/architecture.md`, `docs/ops/dsm6-package-adr.md`, `docs/ops/dsm6-package-layout.md`, `docs/ops/dsm6-runbook.md`:
  - зафиксированы validated host-факты первого DSM smoke: `DSM 6.1.4-15217 Update 1`, `DS3615xs-j`, `x86_64`, `Docker 20.10.3-0554`, `docker-compose 1.28.5`;
  - задокументированы архитектурные ограничения package layer: только `linux/amd64` bundled images, explicit path resolution для `docker/docker-compose`, запрет nested interpolation в `image:` полях и исключение `conf/resource` из DSM 6.1 target;
  - в runbook добавлен troubleshooting case для `exec format error`.

### Tests
- Добавлен backend test zero-preview для empty latest-job action flow.
- Добавлен frontend component test на zero-state `Preview Impact`.

### Validation
- Проверена связность `tasks/OPS-02.md`, `docs/ops/dsm6-package-adr.md`, `STATUS.md` и `CHANGELOG.md` после фиксации `OPS-02.1`.
- `bash -n` для package shell scripts и `scripts/build/build_synology_spk.sh`.
- `bash -n scripts/build/bundle_synology_images.sh`.
- `bash -n scripts/build/check_synology_toolkit.sh`.
- `bash -n scripts/build/build_synology_spk_manual.sh scripts/build/build_synology_spk_in_docker.sh scripts/build/docker/toolkit-entrypoint.sh`.
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m py_compile scripts/build/pack_synology_archive.py`.
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m py_compile scripts/build/generate_synology_icons.py`.
- `python3 scripts/build/generate_synology_icons.py`.
- `bash scripts/build/build_synology_spk.sh --stage-only`.
- `bash scripts/build/bundle_synology_images.sh --clean-output --target-platform linux/amd64` -> собраны архивы `api/frontend/redis`.
- `bash scripts/build/build_synology_spk.sh --stage-only --bundle-images` -> подтвержден единый stage-path с bundled archives.
- `bash scripts/build/check_synology_toolkit.sh --help`.
- `bash scripts/build/build_synology_spk_manual.sh --bundle-images --target-platform linux/amd64` -> собран `artifacts/synology-spk/nas-diff-x64-0.1.0-0008.spk`.
- `tar -xf artifacts/synology-spk/nas-diff-x64-0.1.0-0008.spk` и `tar -xJf package.tgz` -> подтверждена ожидаемая структура root `.spk` и payload.
- `file artifacts/synology-spk/nas-diff-x64-0.1.0-0008.spk` -> `POSIX tar archive (GNU)`.
- Локальная симуляция package target в `/tmp`: `render-runtime-env.sh` и `render-ui-config.sh` корректно рендерят env и DSM launcher URL.

## [2026-03-15] UI-05 + ACT-03 + UI-06 - Simple Scan defaults, last-job bulk action, hamburger navigation

### Added
- Новый API для `Simple Scan`:
  - `GET /api/v1/scan/jobs/latest/processed`;
  - `POST /api/v1/actions/jobs/{job_id}/preview`;
  - `POST /api/v1/actions/jobs/{job_id}/batches`.
- Новые backend tests:
  - `backend/tests/api/test_api_03_scan_jobs_catalog.py` — latest processed job;
  - `backend/tests/api/test_act_01_actions.py` — агрегация distinct `non-primary` file ids по job.
- Новый frontend component test:
  - `frontend/tests/component/app-navigation.test.jsx` для default route и hamburger-menu.

### Changed
- `frontend/src/pages/DashboardPage.jsx`:
  - `Simple Scan` теперь автоподставляет path/mode из последнего processed job;
  - добавлен fallback через `localStorage`/default values;
  - добавлен safe action flow `Preview Impact -> Create Draft Batch -> Confirm Batch` для последнего processed job.
- `frontend/src/App.jsx`:
  - маршрут `/` переключен на `Simple Scan`;
  - `Advanced` перенесен на `/advanced`, `/scan` оставлен alias;
  - `Advanced` и `Review & Actions` перенесены в hamburger-menu с close по outside-click и `Esc`.
- `frontend/src/api/client.js`:
  - добавлены клиенты latest-job defaults и job-scoped actions.
- `frontend/src/styles/global.css`:
  - добавлены стили hamburger-menu, simple defaults card и simple action card.
- `docs/specification.md`:
  - задокументированы новый Simple Scan primary flow и job-scoped actions API.

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_act_01_actions.py backend/tests/api/test_api_03_scan_jobs_catalog.py` -> `15 passed`.
- Ограничение текущего sandbox: `npm` отсутствует (`npm: command not found`), поэтому `vitest`/`playwright` локально не запускались.

## [2026-03-15] TASKS-03 - New briefs for Simple Scan defaults/actions/navigation

### Added
- Новые task briefs:
  - `tasks/UI-05.md` — Simple Scan: автоподстановка последнего каталога и режима.
  - `tasks/ACT-03.md` — Simple Scan: единое действие по всем файлам последнего job.
  - `tasks/UI-06.md` — hamburger-навигация и старт с Simple Scan.

### Changed
- `tasks/README.md`:
  - добавлены новые пункты backlog `19..21`;
  - обновлен список `Файлы задач`.

### Validation
- Проверка структуры briefs на соответствие шаблону `TASK_BRIEF.md`.

## [2026-03-15] UX-SKETCH-01 - Simple Scan screen + Review bulk selection sketch

### Added
- Новый упрощенный экран сканирования:
  - route `"/scan"` в `frontend/src/App.jsx`;
  - `DashboardPage` в режиме `variant="simple"` показывает только:
    - поле пути каталога;
    - выбор режима сканирования;
    - кнопку запуска;
    - компактный progress-bar.
- В `Review & Actions` добавлены элементы для массовой работы:
  - выбор групп для batch (`select for batch`);
  - команды `Select All Groups` / `Clear Selection`;
  - новый scope `selected_groups`;
  - блок `Batch decision for groups` для назначения одного решения всем non-primary файлам выбранных групп;
  - блок `Apply one decision to selected files` для массового назначения одного решения выбранным файлам текущей группы.
- Добавлен component-тест упрощенного режима dashboard:
  - `frontend/tests/component/dashboard-page.test.jsx`.
- Добавлены component-тесты массовых решений в `Review`:
  - `frontend/tests/component/review-page.test.jsx`.

### Changed
- Навигация в topbar:
  - `Advanced` (`/`),
  - `Simple Scan` (`/scan`),
  - `Review & Actions` (`/review`).
- Схема preview/create в `ReviewPage` учитывает marker выбранных групп для `selected_groups`.
- Стили `frontend/src/styles/global.css` расширены для:
  - simple progress card;
  - нового layout в списке групп (`group-row__meta`, `group-row__selector`).

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests frontend/src`.
- `docker compose config`.
- Анализ runtime-логов `frontend/api`:
  - подтвержден регулярный polling `GET /scan/jobs/{job_id}/groups?...` каждые ~5 сек при открытом `Review`.
- Ограничение текущего sandbox: `node/npm` отсутствуют, поэтому `vitest/playwright` локально не запускались.

## [2026-03-15] QA-02 - Regression coverage for roots/jobs/bulk UX

### Added
- Новый backend regression тест:
  - `backend/tests/api/test_qa_02_regression.py` с покрытием:
    - delete root conflict (`409`) при ссылке из scan job;
    - scan jobs list/filter в завершенном scan flow;
    - bulk preview/confirm/execute/rollback сценария.
- Frontend regression расширения:
  - `frontend/tests/component/review-page.test.jsx`:
    - rollback flow после executed `move_to_trash` batch;
    - проверка `all_filtered` scope + preview-first contract.
  - `frontend/tests/e2e/review-actions.spec.js`:
    - добавлен rollback в e2e smoke (`preview -> draft -> confirm -> execute -> rollback`).

### Changed
- `scripts/ci/run_s3_regression_suite.sh`:
  - добавлен fallback-выбор python интерпретатора с установленным `pytest`;
  - добавлен `SKIP_FRONTEND=1` для backend-only прогона;
  - добавлена явная проверка наличия `npm` перед frontend стадиями.

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests frontend/src`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_qa_02_regression.py backend/tests/api/test_api_01_scan_roots.py backend/tests/api/test_api_03_scan_jobs_catalog.py backend/tests/api/test_act_01_actions.py` -> `16 passed`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `35 passed`.
- `docker compose config`.
- `SKIP_FRONTEND=1 SKIP_PLAYWRIGHT=1 bash scripts/ci/run_s3_regression_suite.sh` -> ok.
- Ограничение текущего sandbox: `npm` отсутствует, поэтому `vitest/playwright` не запускались.

## [2026-03-14] ACT-02 - Bulk actions preview, scoped selection и staged destructive confirm

### Added
- Новый API endpoint `POST /api/v1/actions/batches/preview`:
  - предварительный расчет последствий массовой операции;
  - возвращает `action_type`, `file_ids`, `files_count`, `total_bytes`, `estimated_reclaimable_bytes`.
- В `ReviewPage` добавлены bulk scopes:
  - `selected`;
  - `all_in_group`;
  - `all_filtered`.
- Новый обязательный UI-шаг `Preview Impact` перед созданием draft batch.
- Усиленный destructive confirm для `delete_permanent`:
  - checkbox-подтверждение;
  - отдельный confirm-step при `Confirm Batch`.

### Changed
- `backend/app/services/action_service.py`:
  - добавлен preview-flow с валидацией action/file ids;
  - для `restore` preview требует наличие unrestored movement.
- `backend/app/api/routes_actions.py`:
  - добавлена модель/роут сериализации preview ответа и обработка `404/422`.
- `frontend/src/pages/ReviewPage.jsx`:
  - создание draft batch теперь блокируется без preview;
  - расширен execution report (`pending/done/failed/skipped`);
  - rollback доступен как быстрый action только для `move_to_trash` batches в `executed/partially_failed`.
- `frontend/src/api/client.js`:
  - добавлен метод `previewActionBatch(payload)`.
- `docs/specification.md`:
  - `POST /api/v1/actions/batches/preview` переведен из planned в реализованный endpoint.

### Tests
- `backend/tests/api/test_act_01_actions.py`:
  - добавлены тесты preview `counts/bytes` и `restore`-ограничения.
- `frontend/tests/component/review-page.test.jsx`:
  - обновлен flow под preview-first;
  - добавлен кейс `all_filtered` scope.
- `frontend/tests/e2e/review-actions.spec.js`:
  - обновлен smoke-flow с обязательным preview перед draft.

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests frontend/src`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_act_01_actions.py backend/tests/api/test_qa_01_regression.py` -> `6 passed`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `34 passed`.
- `docker compose config`.
- Ограничение текущего sandbox: `node/npm` отсутствуют, поэтому `vitest/playwright` не запускались.

## [2026-03-14] HOTFIX-UI-POLLING-01 + API-03 stale running cleanup

### Added
- API `DELETE /api/v1/scan/jobs/{job_id}` расширен query-параметром `allow_stale_running=true` для удаления stale `queued/running` jobs по явному подтверждению оператора.
- В dashboard jobs table добавлена колонка `Progress` с динамическим progress-bar по каждому job.
- В component test dashboard добавлен сценарий двухшагового удаления stale running job (обычный delete -> retry с `allow_stale_running=true`).

### Changed
- `backend/app/api/routes_scan.py`:
  - удаление `queued/running` job теперь возможно только при двух условиях:
    - передан `allow_stale_running=true`;
    - job старше `SCAN_JOB_TIMEOUT_SECONDS` (stale-check по `started_at`/`requested_at`).
  - для свежих активных jobs возвращается `409` с блокировкой удаления.
- `frontend/src/api/client.js`:
  - `deleteScanJob` поддерживает опцию `{ allowStaleRunning }`.
- `frontend/src/pages/DashboardPage.jsx`:
  - polling больше не делает full reload таблицы jobs;
  - background polling точечно обновляет runtime-поля активных jobs (`status`, counters, reclaimable, error/finished);
  - для `409` по active job добавлен confirm-step и retry удаления stale metadata.
- `frontend/src/styles/global.css`:
  - добавлены стили progress-bar (`jobs-progress*`) с плавным обновлением ширины.
- `backend/tests/api/test_api_03_scan_jobs_catalog.py`:
  - добавлены проверки stale-force-delete и блокировки force-delete для свежего running job.

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests frontend/src`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_api_03_scan_jobs_catalog.py` -> `7 passed`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `32 passed`.
- `docker compose config`.
- Ограничение текущего sandbox: `node/npm` отсутствуют, поэтому `vitest/playwright` не запускались.

## [2026-03-14] UI-03 + UI-04 - Dashboard layout, roots/jobs operations и job journal UX

### Added
- В frontend API client (`frontend/src/api/client.js`) добавлены методы:
  - `deleteScanRoot(rootId)`;
  - `listScanJobs({status, mode, order, page, pageSize})`;
  - `deleteScanJob(jobId)`.
- Новый jobs journal UI на dashboard:
  - таблица jobs с фильтрами/сортировкой/пагинацией;
  - detail panel по выбранному job;
  - display-name формата `SCAN-<MODE>-<SEQ>` + timestamp.
- Поддержка безопасного удаления метаданных из UI:
  - удаление `scan roots` с confirm-step;
  - удаление `scan jobs` с confirm-step и обработкой safe-delete конфликтов.
- Обновлены frontend тесты:
  - `frontend/tests/component/dashboard-page.test.jsx`;
  - `frontend/tests/e2e/scan-launch.spec.js`.

### Changed
- `frontend/src/pages/DashboardPage.jsx`:
  - переработан layout в формат `left health column + right operations column`;
  - добавлен `Scan Roots Registry` с `enabled/delete` действиями;
  - добавлен `Scan Jobs Journal` (table + detail + delete metadata);
  - улучшена обработка API-ошибок (человеко-читаемые сообщения для roots/jobs delete).
- `frontend/src/App.jsx`:
  - добавлен callback `onJobDeleted` для синхронизации recent/active job в local state.
- `frontend/src/components/StatusBadge.jsx`:
  - добавлен статус `canceled`.
- `frontend/src/styles/global.css`:
  - добавлены стили для dashboard columns, health stack, roots registry, jobs toolbar/table/pagination и active-row состояния.

### Validation
- `docker compose config`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `30 passed`.
- Ограничение текущего sandbox: `npm` отсутствует (`npm: command not found`), поэтому `vitest/playwright` не запускались.

## [2026-03-14] API-03 - Каталог scan jobs и безопасное удаление

### Added
- Новый API endpoint `GET /api/v1/scan/jobs`:
  - фильтры по `status` и `mode`;
  - пагинация через `page` и `page_size`;
  - сортировка по `requested_at` (`order=asc|desc`).
- Новый API endpoint `DELETE /api/v1/scan/jobs/{job_id}` с безопасной политикой удаления.
- Новый API-тестовый модуль:
  - `backend/tests/api/test_api_03_scan_jobs_catalog.py`.

### Changed
- `backend/app/db/repositories/scan_jobs.py`:
  - добавлены `list_jobs(...)`, `count_delete_dependencies(job_id)`, `delete(job_id)`;
  - добавлена модель зависимостей удаления `ScanJobDeleteDependencies`.
- `backend/app/api/routes_scan.py`:
  - подключен `GET /scan/jobs`;
  - добавлен `DELETE /scan/jobs/{job_id}` с `404/409/204` контрактом;
  - добавлены проверки безопасного удаления:
    - запрет удаления jobs в `queued/running`;
    - конфликт при наличии `exact_groups`, `similar_groups`, `action_items`.
- `backend/tests/db/test_repositories.py`:
  - добавлены проверки list/pagination и dependency-counters для cleanup scan jobs.
- `backend/app/db/repositories/__init__.py`:
  - экспортирован `ScanJobDeleteDependencies`.

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests/api/test_api_02_scan_jobs.py backend/tests/api/test_api_03_scan_jobs_catalog.py backend/tests/db/test_repositories.py` -> `14 passed`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `30 passed`.
- `docker compose config`.

## [2026-03-13] TASKS-02 - Новый backlog задач API/UI/ACT/QA

### Added
- Новые task briefs:
  - `tasks/API-03.md`;
  - `tasks/UI-03.md`;
  - `tasks/UI-04.md`;
  - `tasks/ACT-02.md`;
  - `tasks/QA-02.md`.

### Changed
- `tasks/README.md`: обновлен порядок backlog и список файлов задач.
- `STATUS.md`: в progress table добавлены новые задачи со статусом `todo`; обновлен ближайший фокус.

### Validation
- Проверка структуры task-файлов на соответствие `TASK_BRIEF.md`.

## [2026-03-13] HOTFIX-SCAN-01 - Таймаут scan jobs, rollback после DB ошибок и batched commits

### Added
- Новая конфигурация таймаута scan jobs:
  - `SCAN_JOB_TIMEOUT_SECONDS` (default `7200`) в `backend/app/config.py`.
- Новые регрессионные тесты:
  - `backend/tests/core/test_scan_orchestrator_failures.py`;
  - `backend/tests/api/test_worker_queue_config.py`.

### Changed
- `backend/app/workers/queue.py`:
  - scan jobs теперь enqueue с явным `job_timeout` из конфигурации.
- `backend/app/services/scan_orchestrator.py`:
  - перед `update_status(...failed...)` добавлен `session.rollback()`;
  - устранено зависание job в `running` после transaction errors.
- `backend/app/core/scanner.py`:
  - сканирование переведено на batched commits (`_COMMIT_BATCH_SIZE=250`) для снижения нагрузки на SQLite.
- `backend/app/db/repositories/files.py` и `file_hashes.py`:
  - добавлен режим `autocommit=False` для batched операций сканера.
- Конфигурация окружения:
  - `.env.example`, `.env.local`, `docker-compose.yml` дополнены `SCAN_JOB_TIMEOUT_SECONDS`.

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `24 passed`.
- `docker compose config`.

## [2026-03-13] UI-01 + UI-02 + QA-01 + OPS-01 - Frontend, regression suite и DSM6 runbook

### Added
- Новый frontend модуль (`React + Vite`) в `frontend/`:
  - страницы `Dashboard` и `Review & Actions`;
  - API client для `health/scan/groups/actions`;
  - UI-компоненты `Panel`, `StatusBadge`, `ErrorBanner`;
  - единая стилизация и адаптивный layout.
- Frontend testing:
  - component tests (`vitest`) для dashboard/review;
  - e2e smoke tests (`playwright`) для scan launch и action workflow.
- Backend regression тест полного цикла:
  - `backend/tests/api/test_qa_01_regression.py`.
- Единый regression runner:
  - `scripts/ci/run_s3_regression_suite.sh`.
- OPS runbook:
  - `docs/ops/dsm6-runbook.md` (install/start/stop/update/backup/restore/troubleshooting).

### Changed
- `docker-compose.yml`: добавлен сервис `frontend` (`nas-diff-frontend:0.1.0`, порт `15173` по умолчанию).
- `.env.example` и `.env.local`: добавлена переменная `FRONTEND_PORT`.
- `.gitignore`: добавлены frontend artifacts (`node_modules`, `dist`, playwright reports/results).

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q backend/tests` -> `24 passed`.
- `docker compose config`.
- Ограничение текущего sandbox: `npm` отсутствует (`npm: command not found`), поэтому `vitest/playwright` не запускались в этом окружении.

## [2026-03-13] ACT-01 - Безопасные batch-действия и rollback

### Added
- API actions:
  - `POST /api/v1/actions/batches`;
  - `GET /api/v1/actions/batches/{batch_id}`;
  - `POST /api/v1/actions/batches/{batch_id}/confirm`;
  - `POST /api/v1/actions/batches/{batch_id}/rollback`.
- Worker execution для action batches:
  - `app.workers.action_worker.process_action_batch`.
- Action queue integration:
  - `ActionQueueClient` / `RQActionQueueClient`;
  - enqueue в `action_queue`.
- Service layer:
  - `backend/app/services/action_service.py` (status machine, execution, rollback).
- Интеграционные API-тесты:
  - `backend/tests/api/test_act_01_actions.py`.

### Changed
- `backend/app/main.py`: подключен роутер `actions`.
- `backend/app/db/models.py`: добавлена ORM-модель `FileMovement`.
- `backend/app/db/repositories/actions.py`: добавлены операции для `file_movements`, restore-marking и batch summary/status helpers.
- `backend/app/workers/queue.py`: добавлена поддержка action queue client.
- `backend/tests/api/conftest.py`: добавлен in-memory action queue override и test-trash каталог в `tmp_path`.

### Validation
- `PYTHONPYCACHEPREFIX=/tmp/python-pycache python3 -m compileall backend/app backend/tests`.
- `docker compose config`.
- `PYTHONPATH=. /tmp/nas-diff-venv/bin/python -m pytest -q` (backend) -> `21 passed`.

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
