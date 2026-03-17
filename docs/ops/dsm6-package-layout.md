# DSM6 Package Layout (OPS-02.2)

Статус: `accepted`  
Дата: `2026-03-15`  
Связанная задача: `OPS-02`

## 1. Цель
Зафиксировать исходную структуру `package/synology-dsm6/`, состав будущего `.spk` и границы между:
- immutable package assets;
- package-managed runtime config;
- persistent application data.

## 2. Драйверы решения
- Поставка должна собираться в `.spk` для DSM 6.1.4 `x86_64`.
- Пакет должен устанавливаться offline через Package Center.
- Приложение должно запускаться из стандартного UI DSM.
- Текущий продукт остается контейнерным (`api`, `worker`, `frontend`, `redis`).
- Uninstall по умолчанию не должен удалять БД, конфигурацию и пользовательские решения.

## 3. Что задает Synology package framework
Официальный Synology package layout требует внутри `.spk` как минимум:
- `INFO`
- `package.tgz`
- `scripts/`
- `conf/`
- `PACKAGE_ICON.PNG`
- `PACKAGE_ICON_256.PNG`

Toolkit workflow рекомендуется строить через `pkgscripts-ng/PkgCreate.py` в два этапа:
- `Build Stage`
- `Pack Stage`

Для DSM desktop integration пакет может регистрировать launcher через `dsmuidir` и `dsmappname`. Каталог, указанный в `dsmuidir`, попадает в `package.tgz` и затем линкуется DSM в `webman/3rdparty` для отображения ярлыка приложения.

Подтвержденные ограничения первого DSM smoke для layout:
- bundled image archives должны быть собраны как `linux/amd64`;
- `payload/images/manifest.env` должен хранить `target_platform=linux/amd64`;
- package runtime должен быть совместим с `docker-compose 1.28.5`;
- `conf/resource` не включается в DSM 6.1 package target.

## 4. Принятое source tree
Исходная структура в репозитории:

```text
package/synology-dsm6/
├── README.md
├── assets/
│   └── README.md
├── conf/
│   └── README.md
├── payload/
│   ├── README.md
│   ├── images/
│   │   └── README.md
│   ├── port_conf/
│   │   └── README.md
│   ├── runtime/
│   │   ├── README.md
│   │   ├── compose/
│   │   │   └── README.md
│   │   ├── env/
│   │   │   └── README.md
│   │   └── scripts/
│   │       └── README.md
│   └── ui/
│       └── README.md
├── scripts/
│   └── README.md
└── SynoBuildConf/
    └── README.md
```

## 5. Назначение каталогов
### `package/synology-dsm6/SynoBuildConf/`
Конфигурация Synology Toolkit:
- `depends`
- `build`
- `install`

На этом этапе каталог создан как skeleton. Его задача в следующем шаге `OPS-02.3`:
- описать, как подготавливаются runtime assets;
- описать, как формируется `package.tgz`;
- описать, как публикуется финальный `.spk`.

### `package/synology-dsm6/scripts/`
Набор lifecycle-скриптов DSM6:
- `preinst`
- `postinst`
- `preuninst`
- `postuninst`
- `preupgrade`
- `postupgrade`
- `start-stop-status`

Эти файлы попадут в root `.spk` как есть.

### `package/synology-dsm6/conf/`
Package-level конфигурация DSM:
- resource config;
- при необходимости port registration;
- другие package framework declarations, которые не относятся к payload.

Для DSM6 эта папка обязательна, но `conf/privilege` не делаем обязательной частью initial scope, потому что требование lower-privilege через `privilege` относится к DSM 7+.
Для DSM 6.1 в `conf/` не добавляется `resource`, потому что Synology resource framework в подтвержденном target приводит к install-time/runtime несовместимости.

### `package/synology-dsm6/assets/`
Исходники package metadata assets:
- `PACKAGE_ICON.PNG`
- `PACKAGE_ICON_256.PNG`
- при необходимости `LICENSE`

Иконка `PACKAGE_ICON.PNG` должна быть подготовлена в размере DSM6.

### `package/synology-dsm6/payload/`
Это исходники того, что будет упаковано в `package.tgz` и извлечено в package target directory.

#### `payload/ui/`
Минимальный DSM launcher layer.

Важно: здесь не дублируется весь React frontend как native DSM app. Вместо этого здесь размещается легкий DSM desktop entry, который:
- регистрируется через `dsmuidir`;
- задает `dsmappname`;
- открывает уже работающий frontend `nas-diff` по package-controlled URL/port.

То есть `payload/ui/` нужен для интеграции в стандартное меню DSM, а не для замены контейнерного frontend.

Текущий scaffold уже содержит:
- `payload/ui/config` как launcher config template с placeholder URL;
- `payload/ui/texts/enu/strings` для базового DSM label/summary;
- `payload/ui/images/diff_*.png` как generated launcher icons.

#### `payload/runtime/compose/`
Package-specific compose/runtime manifests:
- package-tailored compose file;
- service naming, volumes и порты для package режима;
- без привязки к локальному dev workflow.

Текущий scaffold: `payload/runtime/compose/docker-compose.package.yml`.
Дополнительное ограничение: compose manifest должен оставаться совместимым с `docker-compose 1.28.5`, то есть без nested variable expansion в `image:` полях.

#### `payload/runtime/env/`
Шаблоны env/config для package deployment:
- runtime env template;
- defaults для package mode;
- mapping пользовательских значений из package-managed config.

Текущий scaffold: `payload/runtime/env/nas-diff.env.template`.
Дополнительно добавлен `payload/runtime/env/package.conf.example` как исходный package-managed конфиг для оператора DSM.

#### `payload/runtime/scripts/`
Shell wrapper scripts, которые вызываются lifecycle-слоем:
- preflight checks;
- env rendering;
- container start/stop/status helpers;
- image load helpers;
- backup-sensitive upgrade helpers.

Текущий scaffold содержит:
- `common.sh`
- `render-runtime-env.sh`
- `render-ui-config.sh`
- `runtime-preflight.sh`
- `docker-load-images.sh`
- `start-stack.sh`
- `stop-stack.sh`
- `status-stack.sh`

#### `scripts/`
Root-level lifecycle scripts DSM6.

Текущий scaffold содержит:
- `preinst`
- `postinst`
- `preupgrade`
- `postupgrade`
- `preuninst`
- `postuninst`
- `start-stop-status`

#### `payload/images/`
Prebuilt container images или image archives для offline installation.

Принятое решение для package mode:
- не тянуть образы из сети во время install/start;
- готовить package-installable image archives как часть build pipeline.
- собирать образы строго под `linux/amd64` для подтвержденного DSM `x86_64` target.

Это нужно, чтобы install/update можно было выполнить offline и без сетевой зависимости на registry.

#### `payload/port_conf/`
Файлы регистрации service ports в DSM resource layer.

На текущий момент планируется зарегистрировать минимум:
- frontend/public UI port;
- при необходимости API port, если он остается доступным извне package runtime.

## 6. Mapping: source tree -> final `.spk`
```text
package/synology-dsm6/assets/PACKAGE_ICON.PNG       -> PACKAGE_ICON.PNG
package/synology-dsm6/assets/PACKAGE_ICON_256.PNG   -> PACKAGE_ICON_256.PNG
package/synology-dsm6/scripts/*                     -> scripts/*
package/synology-dsm6/conf/*                        -> conf/*
package/synology-dsm6/payload/**                    -> package.tgz/**
Synology Toolkit output                             -> INFO + final .spk
```

`INFO` предполагается генерировать build pipeline'ом из package metadata templates и version/build context, а не редактировать вручную в корне артефакта.

## 7. Границы immutable и persistent данных
### Immutable
Попадает в `package.tgz` и живет в package target:
- launcher assets;
- runtime wrapper scripts;
- compose/env templates;
- bundled image archives;
- служебные статические package files.

### Persistent
Не должен жить внутри `target`, потому что `target` удаляется на uninstall/upgrade-replace.

Для DSM6 package mode принимаем следующую модель:
- package config:
  - `/var/packages/nas-diff/etc/`
- persistent app state:
  - `/var/packages/nas-diff/var/`
- temporary runtime files:
  - `/var/packages/nas-diff/tmp/`

Synology package framework сам маппит эти пути на volume-backed package directories DSM6, поэтому runtime слой работает через стабильные package paths, а не через hardcoded host-specific `@appdata` пути.

### Почему не использовать `target` для SQLite и Redis AOF
- это ломает safe uninstall;
- это создает риск потери БД при package replace/upgrade;
- это противоречит требованию сохранять данные и пользовательские решения по умолчанию.

### Что хранится в persistent app state
- `var/data/nas_diff.db`
- `var/redis/appendonly.aof`
- `var/logs/`
- `var/rendered-env/`
- `var/runtime/`

## 8. Конкретные package-mode overrides относительно текущего docker workflow
Для package режима не используем текущий dev default:
- `HOST_DATA_DIR=~/.nas-diff/data`

Вместо этого runtime wrapper должен рендерить значения вроде:
- `HOST_DATA_DIR=/var/packages/nas-diff/var/data`
- `NAS_MOUNT_PATH=<package-configured path>`
- `FRONTEND_PORT=<package-controlled admin/public port>`

Текущий `docker-compose.yml` репозитория остается dev- и ops-friendly baseline, но package runtime получает отдельный compose/env слой.

## 9. Что должно появиться следующим шагом (`OPS-02.3`)
1. Build wrapper script для сборки `.spk`.
2. `SynoBuildConf/build` и `SynoBuildConf/install`.
3. Package metadata templating для `INFO`.
4. Правила сборки bundled image archives и укладки их в `payload/images/`.
5. Явная фиксация platform metadata для bundled images и compose-совместимости с `docker-compose 1.28.x`.

## 10. Источники
- Synology Package Introduction:
  - https://help.synology.com/developer-guide/synology_package/introduction.html
- Synology package scripts:
  - https://help.synology.com/developer-guide/synology_package/scripts.html
- Synology `package.tgz`:
  - https://help.synology.com/developer-guide/synology_package/package_tgz/package_tgz.html
- Synology Launch an App:
  - https://help.synology.com/developer-guide/synology_package/package_tgz/launch_app.html
- Synology Toolkit:
  - https://help.synology.com/developer-guide/toolkit/toolkit.html
- Synology Desktop Application integration:
  - https://help.synology.com/developer-guide/integrate_dsm/desktopapp.html
- Synology script environment variables:
  - https://help.synology.com/developer-guide/synology_package/script_env_var.html
- Synology Port Config resource:
  - https://help.synology.com/developer-guide/resource_acquisition/port_config.html
