#!/bin/bash

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/common.sh"

status_stack() {
    local running services expected service

    if [ ! -f "${RENDERED_ENV_FILE}" ] || [ ! -f "${COMPOSE_FILE}" ]; then
        exit 3
    fi

    if ! resolve_docker_bin >/dev/null 2>&1 && ! resolve_docker_compose_bin >/dev/null 2>&1; then
        exit 4
    fi

    running="$(run_compose ps --services --filter status=running 2>/dev/null || true)"
    services=" ${running} "
    expected="api frontend worker redis"

    for service in ${expected}; do
        case "${services}" in
            *" ${service} "*) ;;
            *) exit 3 ;;
        esac
    done

    exit 0
}

status_stack
