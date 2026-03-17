set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

env_file := ".env.local"

default:
    @just --list

_ensure-local-env:
    test -f {{env_file}} || { echo "Missing {{env_file}}. Create it before running compose commands."; exit 1; }

init-local:
    mkdir -p "${HOST_DATA_DIR:-$HOME/.nas-diff/data}"
    mkdir -p nas-mock/photo nas-mock/archive nas-mock/.nas-diff-trash

config: _ensure-local-env init-local
    HOST_DATA_DIR="${HOST_DATA_DIR:-$HOME/.nas-diff/data}" docker compose --env-file {{env_file}} config

up: _ensure-local-env init-local
    HOST_DATA_DIR="${HOST_DATA_DIR:-$HOME/.nas-diff/data}" docker compose --env-file {{env_file}} up -d --build

down: _ensure-local-env
    HOST_DATA_DIR="${HOST_DATA_DIR:-$HOME/.nas-diff/data}" docker compose --env-file {{env_file}} down

ps: _ensure-local-env
    HOST_DATA_DIR="${HOST_DATA_DIR:-$HOME/.nas-diff/data}" docker compose --env-file {{env_file}} ps

logs service="api": _ensure-local-env
    HOST_DATA_DIR="${HOST_DATA_DIR:-$HOME/.nas-diff/data}" docker compose --env-file {{env_file}} logs -f {{service}}

health: _ensure-local-env
    HOST_DATA_DIR="${HOST_DATA_DIR:-$HOME/.nas-diff/data}" docker compose --env-file {{env_file}} exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health').read().decode())"

restart: down up

spk-stage:
    bash scripts/build/build_synology_spk.sh --stage-only

spk-build toolkit_dir platform no_sign="--no-sign":
    bash scripts/build/build_synology_spk.sh --toolkit-dir {{toolkit_dir}} --platform {{platform}} {{no_sign}}

spk-icons:
    python3 scripts/build/generate_synology_icons.py

spk-images target_platform="linux/amd64":
    bash scripts/build/bundle_synology_images.sh --target-platform {{target_platform}} --clean-output

spk-stage-images target_platform="linux/amd64":
    bash scripts/build/build_synology_spk.sh --stage-only --bundle-images --target-platform {{target_platform}}

spk-check toolkit_dir platform:
    bash scripts/build/check_synology_toolkit.sh --toolkit-dir {{toolkit_dir}} --platform {{platform}}

spk-build-images toolkit_dir platform no_sign="--no-sign":
    bash scripts/build/build_synology_spk.sh --toolkit-dir {{toolkit_dir}} --platform {{platform}} --bundle-images {{no_sign}}

spk-build-docker platform="bromolow":
    bash scripts/build/build_synology_spk_in_docker.sh --platform {{platform}}

spk-build-manual target_platform="linux/amd64":
    bash scripts/build/build_synology_spk_manual.sh --bundle-images --target-platform {{target_platform}}
