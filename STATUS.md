# STATUS

Актуально на: `2026-03-13`

## 1. Общий статус проекта
- Текущая стадия: базовая инфраструктура backend/worker поднята.
- Продуктовый режим безопасности: `move_to_trash` по умолчанию, `HARD_DELETE_ENABLED=false`.
- Ближайший фокус: реализация `DB-01` (модель данных и миграции).

## 2. Прогресс по backlog
| Task | Статус | Комментарий |
|---|---|---|
| INFRA-01 | done | Выполнен backend scaffold, Docker-окружение, health endpoint и worker startup. |
| DB-01 | todo | Следующий логический шаг после INFRA-01. |
| API-01 | todo | Ожидает DB-layer базовых сущностей. |
| API-02 | todo | Ожидает API-01 и worker orchestration логики. |
| CORE-01 | todo | Не начато. |
| CORE-02 | todo | Не начато. |
| CORE-03 | todo | Не начато. |
| DECISION-01 | todo | Не начато. |
| ACT-01 | todo | Не начато. |
| UI-01 | todo | Не начато. |
| UI-02 | todo | Не начато. |
| QA-01 | todo | Не начато. |
| OPS-01 | todo | Не начато. |

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
- Предупреждение compose: поле `version` считается устаревшим (не блокирует запуск).
- Хостовый smoke-check через `curl 127.0.0.1:18080` в sandbox нестабилен; health подтвержден изнутри контейнера.
- После smoke-check создан `data/nas_diff.db` (локальный sqlite-файл в рабочем каталоге).

## 6. Следующий практический шаг
- Выполнить `tasks/DB-01.md`: подключить схему БД и проверку применимости `database/schema.sql` в SQLite.
