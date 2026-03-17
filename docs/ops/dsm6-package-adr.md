# DSM6 Package ADR (OPS-02.1)

Статус: `accepted`  
Дата: `2026-03-15`  
Связанная задача: `OPS-02`

## 1. Цель
Зафиксировать стартовую архитектуру поставки `nas-diff` как штатного пакета Synology DSM 6.1.4, не ломая текущую контейнерную архитектуру приложения и локальный `docker-compose` workflow разработки.

## 2. Контекст
- Текущая поставка `nas-diff` рассчитана на DSM6 и Docker-based deployment.
- Пользовательский сценарий `OPS-02` требует:
  - установку через Package Center;
  - lifecycle через штатные действия DSM (`install/start/stop/update/uninstall`);
  - запуск UI приложения из стандартного интерфейса Synology;
  - безопасное сохранение БД и пользовательской конфигурации.
- Ключевое ограничение: задача не включает переписывание backend/frontend в нативный стек Synology.
- Подтвержденный target host для первого production-like smoke:
  - `DSM 6.1.4-15217 Update 1`
  - `DS3615xs-j`
  - `x86_64`
  - `Docker 20.10.3-0554`
  - `docker-compose 1.28.5` в `/usr/local/bin/docker-compose`
- Подтвержденные host-specific ограничения:
  - bundled images для package runtime должны быть `linux/amd64`;
  - `docker-compose` v1.28.5 не поддерживает nested variable expansion в `image:` полях;
  - package scripts не могут рассчитывать на тот же `PATH`, что виден в интерактивной SSH-сессии;
  - Synology `conf/resource` не должен включаться в DSM 6.1 package target.

## 3. Решение 1: package toolchain
### Принятое решение
Использовать repository-managed package source tree и воспроизводимую CLI-сборку `.spk` из репозитория. Сборка должна выполняться локальным скриптом-оберткой репозитория, который вызывает официальный Synology package toolchain в non-interactive режиме.

### Почему так
- Сборка должна быть воспроизводимой и пригодной для CI позже.
- Package metadata, scripts и web entry должны version-control'иться вместе с кодом приложения.
- GUI-only workflow для package assembly не подходит: он плохо автоматизируется и хуже проверяется в review.

### Практическая модель
- В репозитории появляется отдельное дерево package source, например `package/synology-dsm6/`.
- В репозитории появляется build entrypoint, например `scripts/build/build_synology_spk.sh`.
- В качестве базового official toolchain используется Synology Package Toolkit с workflow `build stage -> pack stage`, вызываемый через `pkgscripts-ng/PkgCreate.py`.
- Build wrapper отвечает за:
  - подготовку package metadata;
  - упаковку runtime assets;
  - вызов Synology package toolchain;
  - публикацию финального `.spk` в каталог артефактов.

### Что это означает для package source tree
Минимальный состав package source должен опираться на стандартную структуру `.spk`:
- `INFO`
- `package.tgz`
- `scripts/`
- `conf/`
- `PACKAGE_ICON.PNG`
- `PACKAGE_ICON_256.PNG`

Для DSM 6.1 не закладываемся на `WIZARD_UIFILES`, потому что этот механизм относится к более поздней ветке DSM.

### Ограничение решения
На первом проходе пакет целится в проверенный DSM 6.1.4 `x86_64` target семейства тестового NAS. Расширение на дополнительные Synology platform families делается отдельной совместимостью, а не implicit-обещанием текущего этапа.

## 4. Решение 2: lifecycle-модель DSM 6.1
### Принятое решение
Использовать стандартный для Synology package shell lifecycle:
- `preinst`
- `postinst`
- `preuninst`
- `postuninst`
- `preupgrade`
- `postupgrade`
- `start-stop-status`

`start-stop-status` является единой точкой управления runtime, а pre/post-скрипты используются для проверки зависимостей, подготовки каталогов, миграции конфигурации и safe-upgrade логики.

### Распределение ответственности
- `preinst`
  - проверка DSM версии, архитектурной совместимости и наличия Docker runtime;
  - проверка конфликтов по портам и доступности целевых путей.
- `postinst`
  - создание package-controlled каталогов;
  - генерация стартовой конфигурации и env-файлов;
  - регистрация web entry/package metadata для UI.
- `start-stop-status`
  - `start`: запуск runtime-wrapper и контейнерного стека;
  - `stop`: штатная остановка сервисов;
  - `status`: проверка, что обязательные сервисы действительно подняты;
  - `log`: при необходимости проксирование к package/runtime логам.
- `preupgrade`
  - backup-sensitive проверки;
  - валидация совместимости конфигурации и свободного места.
- `postupgrade`
  - миграция env/config templates;
  - restart/health verification.
- `preuninst` / `postuninst`
  - удаление runtime-registration без удаления пользовательских данных по умолчанию.

### Почему так
- Эта модель соответствует стандартному package lifecycle DSM и не требует нестабильных обходных путей.
- Единая точка управления в `start-stop-status` упрощает диагностику и снижает риск расхождения между install/update/start сценариями.
- Pre/post scripts позволяют держать safety checks отдельно от непосредственного запуска контейнеров.
- Это также согласуется с правилом Synology: `pre*`-скрипты используются для проверок и не должны вносить системные side effects.
- Для DSM 6.1 отдельно зафиксированы runtime-ограничения:
  - `start` должен выполнять `docker-compose up -d --force-recreate --remove-orphans`;
  - `docker` и `docker-compose` нужно разрешать через explicit path search, а не через implicit shell `PATH`.

## 5. Решение 3: модель запуска контейнеров
### Принятое решение
Пакет Synology не перепаковывает приложение в нативный сервис DSM. Он выступает как управляющая оболочка над существующим контейнерным стеком `api + worker + frontend + redis`.

Пакетный runtime должен:
- генерировать package-owned env/config;
- запускать и останавливать контейнерный стек;
- хранить persistent data отдельно от immutable package assets;
- не вмешиваться в dev-only `docker-compose` workflow репозитория.

### Практическая модель
- Package assets содержат:
  - package metadata;
  - lifecycle scripts;
  - шаблоны env/config;
  - runtime wrapper scripts;
  - иконки и UI-entry metadata.
- Persistent data хранятся вне package payload и переживают restart/upgrade/uninstall по умолчанию.
- Runtime wrapper вызывает контейнерный запуск через package-controlled compose/config layer, а не через пользовательские ручные команды.
- `package.tgz` используется как контейнер для package-owned runtime assets, которые при установке раскладываются в package target directory.
- Compose manifest package-режима должен быть совместим с `docker-compose 1.28.x`:
  - без nested interpolation в `image:` полях;
  - с финальными image refs, отрендеренными в env-файле.
- Bundled image archives должны фиксировать целевую платформу `linux/amd64` в manifest и собираться только под нее для DSM `x86_64`.

### Почему так
- Это минимально инвазивный путь для текущей архитектуры.
- Он сохраняет уже реализованные сервисные границы и эксплуатационные ожидания.
- Он позволяет валидировать package behavior отдельно от разработки backend/frontend.

### Альтернативы, которые не выбраны
- Полное переписывание приложения под нативный web stack DSM.
  - Отклонено как вне scope и слишком дорого для v1.
- Ручной запуск Docker из README после установки "пустого" пакета.
  - Отклонено, потому что не выполняет цель штатного lifecycle через Package Center.

## 6. Решение 4: модель хранения данных и конфигурации
### Принятое решение
Разделить:
- immutable package assets;
- package-managed runtime config;
- persistent application data.

По умолчанию uninstall не удаляет:
- SQLite базу;
- пользовательские решения;
- runtime logs;
- конфигурацию путей scan roots/trash.

Для DSM 6.1 принимаем стандартную package FHS-модель Synology:
- `/var/packages/nas-diff/etc`
- `/var/packages/nas-diff/var`
- `/var/packages/nas-diff/tmp`

### Почему так
- Это соответствует safety-first политике продукта.
- Это снижает риск потери индекса и истории действий при штатных операциях сопровождения.
- Это опирается на стандартные package directories DSM6 и не требует отдельного DSM7-style design branch.

## 7. Решение 5: модель UI-интеграции с DSM
### Принятое решение
Пакет должен регистрироваться как запускаемое DSM-приложение с иконкой и web entry, который открывает frontend `nas-diff` из стандартного UI Synology.

### Почему так
- Требование `OPS-02` прямо требует запуска из штатного UI, а не только наличие открытого порта.
- Это делает поведение приложения ожидаемым для домашнего администратора NAS.

### Ограничение решения
Если на конкретной модели DSM6 прямой preferred web entry механизм окажется ограничен, допустим fallback на поддерживаемый Synology web portal entrypoint. Но fallback не должен требовать ручного ввода URL как основной сценарий.

## 8. Решение 6: зафиксированные compatibility-факты первого DSM smoke
### Принятое решение
Использовать результаты первого реального DSM smoke как архитектурные ограничения package layer, а не как временные workaround notes.

### Что зафиксировано
- Правильный package image bundle для подтвержденной NAS собирается только как `linux/amd64`.
- `docker-compose` версии `1.28.5` на DSM 6.1:
  - требует отдельной совместимости compose manifest;
  - не эквивалентен `docker compose` plugin из современных Docker Desktop/Linux setups.
- Package runtime обязан искать исполняемые файлы минимум в путях:
  - `/usr/local/bin/docker-compose`
  - `/var/packages/Docker/target/usr/bin/docker`
  - `/usr/local/bin/docker`
- После package upgrade/start необходимо принудительное recreate контейнеров, иначе можно повторно поднять устаревшие контейнеры со старым образом неверной архитектуры.
- `conf/resource` исключается из DSM 6.1 package target.

### Почему так
- Эти факты уже подтверждены на реальном NAS и влияют на install/start behavior.
- Если оставить их только в чат-истории, риск повторной регрессии в package build/runtime слишком высокий.

## 9. Последствия решения
### Положительные
- Появляется четкая граница между package layer и application layer.
- Сборка `.spk` становится воспроизводимой и пригодной для последующей автоматизации.
- Runtime lifecycle стандартизуется вокруг Synology package hooks.

### Негативные
- Появляется отдельный packaging-layer, который нужно поддерживать вместе с контейнерным стеком.
- Совместимость по моделям Synology придется подтверждать отдельно, особенно если package будет масштабироваться шире одного validated target.

## 10. Что делать дальше
1. Реализовать `OPS-02.2`: зафиксировать package source tree и карту package artifacts.
2. Реализовать `OPS-02.3`: добавить build wrapper для сборки `.spk`.
3. Реализовать `OPS-02.4` и `OPS-02.5`: runtime wrapper и DSM lifecycle scripts.

## 11. Внешние референсы
- Synology Package Developer Guide, Package Introduction:
  - https://help.synology.com/developer-guide/synology_package/introduction.html
- Synology Package Developer Guide, scripts:
  - https://help.synology.com/developer-guide/synology_package/scripts.html
- Synology Package Developer Guide, package.tgz:
  - https://help.synology.com/developer-guide/synology_package/package_tgz/package_tgz.html
- Synology Package Developer Guide, Launch an App:
  - https://help.synology.com/developer-guide/synology_package/package_tgz/launch_app.html
- Synology Package Developer Guide, Synology Toolkit:
  - https://help.synology.com/developer-guide/toolkit/toolkit.html
- Synology Package Developer Guide, Your First Package:
  - https://help.synology.com/developer-guide/getting_started/first_package.html
