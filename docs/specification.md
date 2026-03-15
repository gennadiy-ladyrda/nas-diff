# Подробная спецификация v1

## 1. Назначение
Приложение предназначено для поиска и безопасной очистки дублей фотографий в семейном архиве на Synology NAS.

## 2. Область действия
В scope v1:
- Два режима поиска: `Exact`, `Similar`.
- Сканирование выбранных директорий NAS.
- Ревью групп и пакетное выполнение действий.
- Безопасный workflow удаления: сначала корзина/карантин.

Вне scope v1:
- Многопользовательская модель и внешняя авторизация.
- Облачная синхронизация и распределенные кластеры.
- ML-классификация фото по содержимому.

## 3. Персоны и сценарии
1. `Домашний администратор NAS`
- Запускает периодический скан.
- Просматривает exact/similar группы.
- Подтверждает перенос в корзину и, при необходимости, физическое удаление.

## 4. Функциональные требования
### FR-1: Управление источниками
- Добавление/удаление `scan roots`.
- Поддержка исключений по пути/маске (будет в API, UI можно добавить позже).

### FR-2: Запуск сканирования
- Создание `scan_job` с режимом `exact|similar|both`.
- Отображение прогресса и статуса.
- `Simple Scan` использует последний обработанный job для автоподстановки пути и режима.
- При отсутствии истории `Simple Scan` использует локальный fallback (`localStorage`) или дефолт `/nas/photo` + `both`.

### FR-3: Exact поиск
- Детектирование 100% одинаковых файлов по `blake3_full`.
- Формирование групп из 2+ файлов.

### FR-4: Similar поиск
- Детектирование похожих фото по `phash64/dhash64`.
- Порог Hamming distance задается в настройках.

### FR-5: Ревью
- Вывод группы с превью/метаданными.
- Автоматический выбор primary с возможностью ручной переопределения.

### FR-6: Действия
- Создание `draft action batch`.
- Явное подтверждение перед выполнением.
- Режимы: `move_to_trash`, `delete_permanent`, `restore`.

### FR-7: Аудит
- Лог всех действий на уровне файла.
- Отчеты по освобожденному месту.

### FR-8: Каталог и жизненный цикл scan jobs
- Получение списка jobs с фильтрацией по `status/mode` и пагинацией.
- Удаление неактуальных jobs из операционного интерфейса.
- Для зависших `running/queued` jobs допускается явный stale-cleanup (двухшаговое подтверждение в UI + серверная stale-проверка).
- Удаление jobs не затрагивает реальные NAS-файлы (только метаданные индекса и связанных сущностей).

### FR-9: Операционный dashboard UX
- Компактный вертикальный блок `System Health` в левой колонке dashboard.
- Таблица jobs с быстрым обзором (`mode`, `status`, время, ключевые метрики).
- По клику на job показывается отдельная строка/панель детального статуса.
- Для оператора отображается человекочитаемое имя job (display-name), при сохранении технического `job_id`.

### FR-10: Групповые операции над файлами
- Массовые действия для набора файлов (`selected`, `all in group`, `all filtered`).
- Перед confirm обязателен preview последствий (count/bytes/action).
- Для `delete_permanent` требуется усиленный confirm-step.
- Для `move_to_trash` доступен rollback-сценарий после исполнения.

### FR-11: Primary navigation и Simple Scan flow
- Маршрут по умолчанию (`/`) открывает `Simple Scan`.
- Доступ к `Advanced` и `Review & Actions` выполняется через hamburger-меню.
- Меню поддерживает активный маршрут, закрытие по клику вне области и по `Esc`.

## 5. Нефункциональные требования
### NFR-1: Совместимость
- DSM6, x86, Docker.

### NFR-2: Безопасность
- `move_to_trash` по умолчанию.
- `delete_permanent` разрешен только при `HARD_DELETE_ENABLED=true` и подтверждении пользователя.

### NFR-3: Производительность
- Сканирование архивов порядка тысяч файлов в пределах часов, не дней.
- Ограничение числа воркеров и CPU/IO.

### NFR-4: Надежность
- После перезапуска контейнеров состояние задач и индекса сохраняется.

### NFR-5: Наблюдаемость
- Структурированные логи.
- API endpoint для health и статусов.

### NFR-6: Операционная управляемость
- Оператор должен быстро найти проблемный job по таблице и детальному статусу.
- Массовые операции должны быть безопасными по умолчанию и прозрачными по последствиям.

## 6. Конфигурация
Обязательные параметры окружения:
- `NAS_SCAN_ROOTS`
- `NAS_TRASH_DIR`
- `REDIS_URL`

Опциональные:
- `HOST_DATA_DIR` (default: `${HOME}/.nas-diff/data`, используется docker-compose для bind mount в `/data`)
- `DATABASE_URL` (default: `sqlite:////data/nas_diff.db` в контейнере, либо автогенерация из `APP_DATA_DIR` вне Docker)
- `APP_DATA_DIR` (default: `~/.nas-diff/data`, используется приложением для локального sqlite path вне Docker)
- `PHASH_DISTANCE_THRESHOLD` (default: 8)
- `MAX_SCAN_WORKERS` (default: 2)
- `SCAN_JOB_TIMEOUT_SECONDS` (default: 7200, timeout одного scan job в RQ)
- `DEFAULT_FILE_ACTION` (default: move_to_trash)
- `HARD_DELETE_ENABLED` (default: false)
- `DB_ALLOW_DESTRUCTIVE_MIGRATIONS` (default: false)

Локальный запуск:
- Рекомендуется профиль `.env.local` и команды из `justfile`.
- Перед стартом локальные каталоги подготавливаются через `just init-local`.

## 7. API v1 (черновой контракт)
### Health
- `GET /api/v1/health`
- Ответ: версия, статус БД, статус очереди

### Scan Jobs
- `POST /api/v1/scan/jobs`
- Тело: `{ mode, roots[], options }`
- Ответ: `{ job_id, status }`

- `GET /api/v1/scan/jobs?status=&mode=&page=&page_size=`
- Ответ: пагинированный список jobs для таблицы в UI

- `GET /api/v1/scan/jobs/{job_id}`
- Ответ: прогресс и метрики

- `GET /api/v1/scan/jobs/latest/processed`
- Ответ: последний обработанный job (`status != queued|running`) с attached roots для `Simple Scan`

- `DELETE /api/v1/scan/jobs/{job_id}`
- Удаление job-метаданных (safe-first; без воздействия на NAS-файлы)
- Для stale `running/queued` jobs поддерживается `allow_stale_running=true` (иначе `409`)

- `GET /api/v1/scan/jobs/{job_id}/groups?kind=exact|similar`
- Ответ: пагинированный список групп

### Groups
- `GET /api/v1/groups/{kind}/{group_id}`
- Ответ: список файлов в группе, scoring, рекомендованный primary

- `POST /api/v1/groups/{kind}/{group_id}/decision`
- Тело: `{ file_id, decision }`

### Actions
- `POST /api/v1/actions/batches/preview`
- Возвращает последствия массовой операции до confirm (`files_count`, `total_bytes`, `estimated_reclaimable_bytes`)

- `POST /api/v1/actions/jobs/{job_id}/preview`
- Возвращает preview для всех distinct `non-primary` файлов exact/similar групп указанного job

- `POST /api/v1/actions/jobs/{job_id}/batches`
- Создает draft batch для всех distinct `non-primary` файлов exact/similar групп указанного job

- `POST /api/v1/actions/batches`
- Создает draft batch

- `POST /api/v1/actions/batches/{batch_id}/confirm`
- Подтверждает запуск

- `GET /api/v1/actions/batches/{batch_id}`
- Возвращает статус выполнения и ошибки

- `POST /api/v1/actions/batches/{batch_id}/rollback`
- Пытается восстановить файлы, перемещенные в корзину

## 8. Фоновая обработка
Очереди:
- `scan_queue`: scan jobs
- `action_queue`: action batches

Идемпотентность:
- Повторный запуск одного `job_id` не должен приводить к дублям записей.
- `action_item` выполняется максимум один раз.

## 9. Правила выбора primary (начальные)
Скоринг файла:
- `+5`: максимальное разрешение в группе
- `+3`: максимальный размер файла
- `+2`: присутствует EXIF дата
- `+1`: более ранняя дата появления в архиве

Файл с лучшим score получает `is_primary=1`.

## 10. Error handling
- Недоступный путь NAS -> `scan_job.status=failed` + `error_message`.
- Файл изменился во время операции -> `action_item.status=failed`.
- Нет прав на перемещение/удаление -> soft-fail в batch с деталями.

## 11. Тестирование v1
Минимальный набор:
- Unit: hashing, grouping, scoring.
- Integration: полный цикл scan -> groups -> action batch -> execute.
- Regression: rollback после move_to_trash.
- UI integration: таблица jobs, detail-row и delete-root/delete-job сценарии.
- E2E smoke: bulk preview -> confirm -> execute -> rollback.

## 12. Релизная стратегия
1. Alpha: только Exact + ручной review.
2. Beta: Similar + порог и сравнение.
3. GA v1: инкрементальный скан, отчетность, rollback.
