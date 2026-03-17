#!/bin/bash

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/common.sh"

start_stack() {
    ensure_package_config
    load_package_config
    run_compose up -d --force-recreate --remove-orphans
    log "Container stack started"
}

start_stack
