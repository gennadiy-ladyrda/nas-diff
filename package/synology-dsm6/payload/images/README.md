# Bundled Images

Здесь размещаются prebuilt container image archives для offline installation.

Текущий формат артефактов:
- `nas-diff-api-<version>.tar`
- `nas-diff-frontend-<version>.tar`
- `redis-<tag>.tar`
- `manifest.env`

Архивы генерируются командой:
- `bash scripts/build/bundle_synology_images.sh --clean-output`

Интеграционный stage-path:
- `bash scripts/build/build_synology_spk.sh --stage-only --bundle-images`

Build artifacts не должны коммититься в git; для этого добавлен локальный `.gitignore`.
