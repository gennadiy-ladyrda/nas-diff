# Synology DSM6 Package Source Tree

Этот каталог содержит исходники package layer для `nas-diff` под Synology DSM 6.1.4.

Ожидаемая роль каталогов:
- `INFO.sh` — package metadata для генерации `INFO`
- `SynoBuildConf/` — конфигурация Synology Toolkit (`depends`, `build`, `install`)
- `assets/` — package icons и другие root-level assets `.spk`
- `conf/` — package framework config
- `scripts/` — lifecycle scripts DSM6
- `payload/` — содержимое будущего `package.tgz`

Текущий scaffold уже содержит:
- build wrapper entrypoint: `scripts/build/build_synology_spk.sh`
- toolkit validator: `scripts/build/check_synology_toolkit.sh`
- package runtime payload: `payload/runtime/*`
- DSM launcher config template: `payload/ui/config`
- generated `DIFF` icons для package root и launcher assets
- bundled image pipeline for offline package install

Детальная схема и карта артефактов описаны в:
- `docs/ops/dsm6-package-layout.md`
- `docs/ops/dsm6-package-adr.md`
