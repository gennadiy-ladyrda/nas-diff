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
