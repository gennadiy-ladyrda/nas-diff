# OPS-02

## 1. Задача
- Краткое название: Synology DSM6 package и запуск из штатного UI
- Цель (что должно измениться в системе): Подготовить приложение к поставке как штатный пакет Synology DSM 6.1.4 (`.spk`), устанавливаемый и управляемый через стандартный интерфейс NAS.
- Ожидаемый результат в 1-2 предложениях: Оператор устанавливает `nas-diff` через Package Center, запускает и останавливает его штатными средствами DSM, а вход в UI приложения доступен из стандартного меню Synology без ручного ввода URL.

## 2. Scope
- Входит в задачу:
  - Формат поставки `.spk` для DSM 6.1.4 `x86_64`.
  - Package lifecycle: `install`, `start`, `stop`, `status`, `upgrade`, `uninstall`.
  - Интеграция со штатным UI DSM: иконка/точка входа в Main Menu или desktop shortcut, открывающая `nas-diff`.
  - Упаковка и orchestration текущих сервисов (`api`, `worker`, `frontend`, `redis`) в модели, совместимой с Synology package workflow.
  - Создание и сохранение package-specific конфигурации, путей данных и mount-параметров NAS.
  - Безопасная политика обновления и uninstall с сохранением данных по умолчанию.
- Не входит в задачу:
  - Переписывание backend/frontend в нативный стек Synology.
  - Поддержка DSM7 раньше DSM6.1.4.
  - Расширение продуктового функционала dedup/action beyond packaging/integration.

## 3. Контекст
- Связанные документы/файлы: `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `.env.example`, `docs/architecture.md`, `docs/ops/dsm6-runbook.md`.
- Текущие ограничения окружения (DSM6, Docker, пути NAS и т.д.): DSM 6.1.4-15217 Update 1, `x86_64`, модель `DS3615xs-j`, один NAS в локальной сети, существующая архитектура уже рассчитана на Docker-based deployment.
- Зависимости/интеграции: Synology Package Center, package scripts DSM6, Docker/Container runtime на NAS, web entrypoint/portal integration для открытия UI из стандартного интерфейса DSM.

## 4. Требования
- Функциональные требования:
  - Репозиторий должен собирать воспроизводимый `.spk`-артефакт для DSM 6.1.4 `x86_64`.
  - Установка пакета должна проверять наличие необходимых системных зависимостей и давать понятную ошибку, если среда не готова.
  - После установки пакет должен поднимать приложение штатным lifecycle-механизмом DSM без ручного запуска `docker compose`.
  - Приложение должно появляться в стандартном UI Synology как запускаемое приложение и открываться по клику.
  - Обновление пакета должно сохранять SQLite-данные, пользовательские решения и безопасные настройки.
  - Удаление пакета не должно уничтожать пользовательские данные без явного режима purge/confirm.
  - Базовая конфигурация путей (`HOST_DATA_DIR`, scan roots, trash dir, published UI endpoint) должна задаваться из package-controlled конфигурации.
- Нефункциональные требования (производительность, безопасность, UX):
  - После установки оператору не требуется shell-доступ для типового запуска и остановки.
  - Ошибки package lifecycle должны быть диагностируемыми через логи и статус в DSM UI.
  - Решение должно сохранить safe-by-default модель: `move_to_trash` по умолчанию, `delete_permanent` отключен до явного разрешения.
  - Packaging-слой не должен ломать текущую контейнерную архитектуру и должен допускать локальную разработку через существующий `docker-compose` workflow.
- Ограничения по безопасности данных:
  - Никаких destructive-migration действий в install/upgrade scripts без явного backup/rollback плана.
  - Uninstall по умолчанию сохраняет индекс, логи и пользовательские решения.
  - Настройки пакета не должны автоматически включать `HARD_DELETE_ENABLED=true`.

## 5. Критерии приемки
1. На Synology DSM 6.1.4-15217 Update 1 `x86_64` пакет устанавливается через Package Center, отображается в стандартном UI и запускается без ручных shell-команд.
2. Клик по приложению в DSM UI открывает рабочий frontend `nas-diff`, а backend health-check подтверждает корректный запуск всех обязательных компонентов.
3. Сценарий upgrade сохраняет пользовательские данные и конфигурацию, а stop/start/uninstall выполняются через стандартные действия Package Center.

## 6. Проверки и тесты
- Какие проверки обязательны:
  - Проверка структуры package-артефакта и корректности DSM lifecycle scripts.
  - `docker compose config` для базовой контейнерной конфигурации, которую package использует как runtime foundation.
  - Smoke install/start/open/stop/update/uninstall на DSM 6.1.4 test host.
- Какие тесты нужно запустить:
  - Проверки package build scripts.
  - Smoke API/UI после запуска пакета.
  - Проверка сохранности SQLite/конфигурации после upgrade.
- Что считается успешной валидацией:
  - Пакет штатно управляется из DSM UI, UI приложения открывается из Synology launcher, данные сохраняются после restart/upgrade.

## 7. Риски
- Основные риски:
  - Ограничения DSM6 package tooling и различия между моделями Synology по поддержке Docker/runtime integration.
  - Конфликт портов, reverse-proxy/portal registration и прав доступа к NAS-путям.
  - Сложность безопасного upgrade path при изменении package scripts и persistent directories.
- Что делать при отклонении/ошибке:
  - Зафиксировать compatibility matrix по моделям DSM6/x86.
  - Разделить package runtime и data directories с явным backup/rollback сценарием.
  - При невозможности прямого UI-launch через выбранный механизм подготовить fallback через поддерживаемый Synology web portal entrypoint, не меняя цели задачи.

## 8. Уровень неопределенности
Оценка `U = (R + T + D + S) / 4`:
- `R` (requirements): 0.08
- `T` (technical): 0.10
- `D` (data/environment): 0.10
- `S` (safety impact): 0.06
- Итог `U`: 0.085

Если `U > 0.1`, перед реализацией нужны уточнения.

## 9. Формат результата
- Какие артефакты ожидаются (код, конфиги, docs): package source/build scripts, DSM lifecycle scripts, package config templates, обновленная ops-документация по install/upgrade/uninstall.
- Какой отчет нужен в финале: ссылка на собранный `.spk`, результат smoke-install на DSM 6.1.4, перечень ограничений совместимости и подтверждение безопасного upgrade/uninstall behavior.

## 10. План реализации и подзадачи
1. `OPS-02.1` - Выбор package toolchain и lifecycle-модели DSM 6.1.x.
   - Рекомендуемый путь: repository-managed package source tree + локальный build script для сборки `.spk`, без зависимости от ручных GUI-инструментов.
   - Рекомендуемая lifecycle-модель: shell-скрипты DSM6 (`install/start/stop/status/upgrade/uninstall`) как управляющий слой над текущими контейнерами приложения.
   - Результат: ADR/tech note с зафиксированными решениями по структуре package, точкам входа lifecycle и модели запуска `api/worker/frontend/redis`.
   - Статус: `done`, см. `docs/ops/dsm6-package-adr.md`.

2. `OPS-02.2` - Спроектировать package layout и структуру артефактов.
   - Определить каталоги package source, шаблоны metadata, иконки, conf-файлы, web entry и bundle-артефакты.
   - Разделить immutable package assets и persistent data/config directories.
   - Результат: согласованная структура каталогов и карта того, что попадает в `.spk`, а что хранится вне пакета.
   - Статус: `done`, см. `docs/ops/dsm6-package-layout.md` и `package/synology-dsm6/`.

3. `OPS-02.3` - Реализовать build pipeline для `.spk`.
   - Добавить reproducible script/Make target для сборки package из репозитория.
   - Включить подготовку docker assets, package metadata и финального архива.
   - Результат: команда сборки, которая на выходе дает версионированный `.spk`.
   - Статус: `done`, см. `scripts/build/build_synology_spk.sh`, `scripts/build/build_synology_spk_manual.sh`, `scripts/build/build_synology_spk_in_docker.sh`, `scripts/build/check_synology_toolkit.sh`, `scripts/build/generate_synology_icons.py`, `package/synology-dsm6/INFO.sh`, `package/synology-dsm6/SynoBuildConf/`, `package/synology-dsm6/payload/runtime/`.
   - Подтвержденный результат: собран локальный артефакт `artifacts/synology-spk/nas-diff-x64-0.1.0-0008.spk` с bundled `linux/amd64` images для DSM 6.1.4 и принудительным recreate контейнеров на старте.
   - Примечание: для текущего no-compile пакета быстрым рабочим путем является manual `.spk` assembly, а toolkit-driven build остается опциональной проверкой official toolchain.

4. `OPS-02.4` - Реализовать runtime-wrapper для контейнерного стека.
   - Подготовить package-managed env/config generation для текущих сервисов.
   - Зафиксировать способ запуска контейнеров из package scripts, не ломающий существующий `docker-compose` dev workflow.
   - Результат: runtime wrapper и package-level конфигурация, достаточные для install/start/stop/status.
   - Статус: `in_progress`, см. `package/synology-dsm6/payload/runtime/scripts/` и `package/synology-dsm6/payload/runtime/env/package.conf.example`.

5. `OPS-02.5` - Реализовать DSM6 lifecycle scripts.
   - Покрыть сценарии `install`, `start`, `stop`, `status`, `upgrade`, `uninstall`.
   - Отдельно обработать preflight checks: доступность Docker runtime, свободные порты, writable data dir, валидность mount paths.
   - Результат: package scripts с диагностируемыми кодами ошибок и логированием.
   - Статус: `in_progress`, см. `package/synology-dsm6/scripts/`.

6. `OPS-02.6` - Интегрировать приложение в стандартный UI DSM.
   - Добавить package icon, display metadata и web entrypoint для открытия frontend из Main Menu/Desktop.
   - Зафиксировать published URL/port и механизм, через который DSM ведет пользователя в UI приложения.
   - Результат: установленный пакет виден и запускается из стандартного UI Synology.

7. `OPS-02.7` - Спроектировать safe storage/config policy.
   - Определить package-controlled пути для SQLite, логов, temp/runtime и конфигурации scan roots/trash.
   - Обеспечить uninstall-safe поведение: данные сохраняются по умолчанию, purge выделен отдельно.
   - Результат: документированная модель хранения и миграции конфигурации между версиями.

8. `OPS-02.8` - Реализовать upgrade/rollback сценарии.
   - Добавить backup-sensitive шаги для upgrade и проверки совместимости конфигурации.
   - Проверить, что package update не теряет БД, пользовательские решения и safe defaults.
   - Результат: воспроизводимый upgrade flow и rollback notes при ошибке обновления.

9. `OPS-02.9` - Валидация на DSM 6.1.4 и эксплуатационная документация.
   - Прогнать smoke: install -> start -> open UI -> health -> stop -> start -> upgrade -> uninstall.
   - Обновить runbook для Package Center сценария, диагностики lifecycle-ошибок и правил сохранения данных.
   - Результат: подтвержденный smoke-report и ops-документация для package deployment.
   - Промежуточный артефакт: `docs/ops/dsm6-package-build-handoff.md` с офлайн-командами для build host и DSM host.

## 11. Порядок выполнения
1. Сначала закрыть `OPS-02.1` как архитектурное решение; без этого реализация package scripts и build pipeline будет рискованной.
2. Затем выполнить `OPS-02.2` и `OPS-02.3`, чтобы зафиксировать package layout и воспроизводимую сборку.
3. После этого реализовать runtime/lifecycle слой (`OPS-02.4`, `OPS-02.5`) и только затем UI-интеграцию (`OPS-02.6`).
4. Завершать задачу нужно storage/upgrade-политикой и DSM smoke (`OPS-02.7`..`OPS-02.9`).
