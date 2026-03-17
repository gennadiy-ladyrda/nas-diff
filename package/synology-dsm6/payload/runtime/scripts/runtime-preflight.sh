#!/bin/bash

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/common.sh"

check_port_free() {
    local port="$1"

    if command -v servicetool >/dev/null 2>&1; then
        if servicetool --conf-port-conflict-check --tcp "${port}" 2>/dev/null | grep -q 'IsConflict: true'; then
            fail "Port conflict detected for TCP ${port}"
        fi
    fi
}

check_path_writable() {
    local path="$1"

    mkdir -p "${path}"
    [ -w "${path}" ] || fail "Path is not writable: ${path}"
}

run_preflight() {
    resolve_docker_bin >/dev/null 2>&1 || fail "Docker binary not found"
    ensure_package_dirs
    check_path_writable "${CONFIG_DIR}"
    check_path_writable "${DATA_DIR}"
    check_path_writable "${REDIS_DIR}"
    check_port_free "${NAS_DIFF_FRONTEND_PORT:-15173}"
    check_port_free "${NAS_DIFF_API_PORT:-18080}"
    log "Runtime preflight checks passed"
}

run_preflight
