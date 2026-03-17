# NAS Diff - Технический Blueprint v1

## 1. Цель v1
Собрать рабочую baseline-версию приложения для Synology NAS (DSM6, x86) с двумя режимами поиска:
- `Exact` (точные дубликаты)
- `Similar` (похожие фотографии)

Ключевой принцип безопасности: по умолчанию файл не удаляется физически, а перемещается в корзину/карантин. Постоянное удаление разрешено только после явного подтверждения.

## 2. Технологический стек
- Backend API: `Python 3.11`, `FastAPI`, `Pydantic`
- Фоновые задачи: `RQ` + `Redis`
- Хранилище индекса: `SQLite`
- UI: `React + Vite` (или SSR-шаблоны на первом этапе)
- Контейнеризация: `Docker Compose` (совместимо с DSM6)

## 2.1 Операционные решения
- Каталог с SQLite на хосте вынесен в home пользователя: `~/.nas-diff/data` (через `HOST_DATA_DIR`).
- Для локальной эксплуатации используется `justfile` (`up/down/ps/logs/health/config`).

## 2.2 Следующий этап UX/Operations
- Dashboard: компактный вертикальный health-блок слева и jobs table как основной центр мониторинга.
- Jobs lifecycle: API и UI для list/delete jobs с safe-first политикой удаления.
- Human-friendly job naming: display-name на основе `mode + sequence + timestamp`.
- Bulk actions: preview последствий + staged-confirm (особенно для destructive режимов).

## 3. Целевая структура репозитория
```text
nas-diff/
├── docker-compose.yml
├── .env.example
├── LICENSE
├── docs/
│   ├── blueprint-v1.md
│   ├── architecture.md
│   ├── specification.md
│   └── database-schema.md
├── database/
│   └── schema.sql
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── routes_health.py
│   │   │   ├── routes_scan.py
│   │   │   ├── routes_scan_jobs.py
│   │   │   ├── routes_groups.py
│   │   │   └── routes_actions.py
│   │   ├── core/
│   │   │   ├── scanner.py
│   │   │   ├── hasher_exact.py
│   │   │   ├── hasher_similar.py
│   │   │   ├── dedup_exact.py
│   │   │   ├── dedup_similar.py
│   │   │   └── decision_engine.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   ├── models.py
│   │   │   └── migrations/
│   │   ├── workers/
│   │   │   ├── queue.py
│   │   │   ├── scan_worker.py
│   │   │   └── action_worker.py
│   │   └── services/
│   │       ├── group_service.py
│   │       └── action_service.py
│   └── tests/
│       ├── test_exact_mode.py
│       ├── test_similar_mode.py
│       ├── test_actions.py
│       └── test_scan_jobs_lifecycle.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── pages/
        ├── components/
        ├── api/
        └── state/
```

## 4. Контуры ответственности
- `api`: REST-контракт для UI и оркестрации задач.
- `core`: алгоритмы сканирования, хэширования и кластеризации дублей.
- `workers`: длительные операции (скан, пересчет групп, применение действий).
- `db`: слой хранения индекса, решений и истории действий.
- `frontend`: операторский интерфейс локального пользователя.

## 5. Этапы реализации v1
1. `Infrastructure`: Docker, конфигурация путей NAS, health-check.
2. `Exact Mode`: индексация и точные группы.
3. `Action Safety`: перенос в корзину, подтверждение, журнал.
4. `Similar Mode`: perceptual hashes и интерфейс сравнения.
5. `Incremental Scan`: ускорение повторных проходов.
6. `Reports`: оценка высвобождаемого места и отчет.
7. `Operational UX`: jobs table, cleanup-flow, roots management и bulk actions safety.

## 6. Definition of Done для v1
- Запуск в DSM6 через `docker-compose up -d`.
- Два режима поиска доступны в UI и API.
- Поддержан безопасный workflow: draft -> confirm -> execute.
- Есть восстановление файлов, перемещенных в корзину приложением.
- Есть журнал действий и базовые интеграционные тесты.
