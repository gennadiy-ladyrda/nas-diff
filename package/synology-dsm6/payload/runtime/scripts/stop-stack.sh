#!/bin/bash

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/common.sh"

stop_stack() {
    if [ ! -f "${RENDERED_ENV_FILE}" ] || [ ! -f "${COMPOSE_FILE}" ]; then
        log "Rendered env or compose file not found; nothing to stop"
        exit 0
    fi

    run_compose down --remove-orphans
    log "Container stack stopped"
}

stop_stack
