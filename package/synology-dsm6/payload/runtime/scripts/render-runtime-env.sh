#!/bin/bash

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/common.sh"

render_env() {
    local nas_host

    ensure_package_config
    load_package_config
    require_path "${ENV_TEMPLATE}"

    nas_host="$(resolve_nas_host)"

    sed \
        "s#__NAS_HOST__#${nas_host}#g" \
        "${ENV_TEMPLATE}" > "${RENDERED_ENV_FILE}"
    chmod 600 "${RENDERED_ENV_FILE}"
    cp -f "${RENDERED_ENV_FILE}" "${TARGET_ENV_FILE}"
    chmod 600 "${TARGET_ENV_FILE}"

    log "Rendered runtime env to ${RENDERED_ENV_FILE} and ${TARGET_ENV_FILE}"
}

render_env
