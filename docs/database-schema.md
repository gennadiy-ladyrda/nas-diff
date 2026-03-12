# Схема БД (SQLite)

Актуальный DDL находится в файле `database/schema.sql`.

## 1. Ключевые сущности
1. `scan_roots`
- Список директорий NAS для сканирования.

2. `scan_jobs`
- Запуски сканов (`exact`, `similar`, `both`) и их метрики.

3. `files`
- Индекс файлов (путь, размер, времена, базовые EXIF-поля).

4. `file_hashes`
- Отпечатки файла (`blake3_full`, `dhash64`, `phash64`).

5. `exact_groups` + `exact_group_items`
- Группы точных дублей и состав каждой группы.

6. `similar_groups` + `similar_group_items`
- Группы похожих файлов и дистанции до anchor.

7. `user_decisions`
- Решения пользователя по каждому файлу в группе.

8. `action_batches` + `action_items`
- Подтверждаемые пакетные действия и статусы исполнения.

9. `file_movements`
- История перемещений для rollback/restore.

## 2. Связи
- Один `scan_job` связан с несколькими `scan_roots` через `scan_job_roots`.
- Один `file` относится к одному `scan_root`.
- Один `file` имеет несколько `file_hashes` (по типам хэша).
- Одна группа (`exact`/`similar`) содержит много файлов через таблицу items.
- Один `action_batch` содержит много `action_items`.
- Один `action_item` указывает на один `file`.
- `file_movements` связывает файл и batch для восстановления.

## 3. Индексы
- Поиск exact дублей: `idx_file_hashes_lookup(hash_type, hash_hex)`.
- Предфильтр по размеру: `idx_files_size(size_bytes)`.
- Выборка по scan root/path: `idx_files_root_rel_path(root_id, rel_path)`.
- Similar review: `idx_similar_group_items_distance(group_id, distance_to_anchor)`.
- Мониторинг действий: `idx_action_items_batch_status(batch_id, status)`.

## 4. Инварианты
- `files.abs_path` уникален.
- Для каждого файла тип хэша уникален: `(file_id, hash_type)`.
- Для группы уникален состав по первичному ключу `(group_id, file_id)`.
- `action_item` уникален в рамках batch: `(batch_id, file_id)`.

## 5. Жизненный цикл данных
1. `scan_job` создается в `queued`.
2. Во время скана обновляются `files`, `file_hashes`.
3. После скана формируются `exact_groups`/`similar_groups`.
4. Пользователь фиксирует `user_decisions`.
5. Создается и исполняется `action_batch`.
6. Для move/restore пишутся записи `file_movements`.

## 6. Размещение SQLite файла
- В Docker: `DATABASE_URL=sqlite:////data/nas_diff.db`.
- На хосте `/data` маппится в `HOST_DATA_DIR` (по умолчанию `~/.nas-diff/data`).
- Файлы БД не хранятся в git-репозитории (`data/` исключен через `.gitignore`).
- Для локального запуска рекомендуется `.env.local` и команды из `justfile`.
