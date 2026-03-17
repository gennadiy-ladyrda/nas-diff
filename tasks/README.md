# Task Backlog

Список задач сформирован по шаблону `TASK_BRIEF.md`.
Разбиения на спринты нет; порядок ниже отражает логические зависимости.

1. `INFRA-01` - Базовый каркас backend/worker и контейнеров
2. `DB-01` - Модель данных и миграции
3. `API-01` - Health и управление источниками сканирования
4. `API-02` - Оркестрация scan jobs и статусы
5. `CORE-01` - Сканер файлов и инкрементальная индексация
6. `CORE-02` - Exact режим (точные дубли)
7. `CORE-03` - Similar режим (похожие фото)
8. `DECISION-01` - Правила выбора primary и пользовательские решения
9. `ACT-01` - Безопасные batch-действия и rollback
10. `UI-01` - Dashboard и экран запуска сканирования
11. `UI-02` - Ревью групп и центр действий
12. `QA-01` - Автотесты и регрессионные сценарии
13. `OPS-01` - Эксплуатация и runbook для DSM6
14. `API-03` - Каталог scan jobs и безопасное удаление
15. `UI-03` - Dashboard layout и управление scan roots
16. `UI-04` - Таблица jobs, status-row и человекочитаемые имена
17. `ACT-02` - Групповые операции над файлами (safe-by-default)
18. `QA-02` - Регрессия для roots/jobs/bulk UX
19. `UI-05` - Simple Scan: автоподстановка последнего каталога и режима
20. `ACT-03` - Simple Scan: одно действие по всем файлам последнего job
21. `UI-06` - Навигация через hamburger и старт с Simple Scan
22. `OPS-02` - Synology DSM6 package (`.spk`) и запуск из штатного UI

## Файлы задач
- `tasks/INFRA-01.md`
- `tasks/DB-01.md`
- `tasks/API-01.md`
- `tasks/API-02.md`
- `tasks/CORE-01.md`
- `tasks/CORE-02.md`
- `tasks/CORE-03.md`
- `tasks/DECISION-01.md`
- `tasks/ACT-01.md`
- `tasks/UI-01.md`
- `tasks/UI-02.md`
- `tasks/QA-01.md`
- `tasks/OPS-01.md`
- `tasks/API-03.md`
- `tasks/UI-03.md`
- `tasks/UI-04.md`
- `tasks/ACT-02.md`
- `tasks/QA-02.md`
- `tasks/UI-05.md`
- `tasks/ACT-03.md`
- `tasks/UI-06.md`
- `tasks/OPS-02.md`
