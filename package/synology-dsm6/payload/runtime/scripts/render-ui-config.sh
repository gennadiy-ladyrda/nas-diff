#!/bin/bash

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/common.sh"

UI_CONFIG_TEMPLATE="${PKG_TARGET}/ui/config"

render_ui_config() {
    local nas_host
    local ui_url

    require_path "${UI_CONFIG_TEMPLATE}"

    nas_host="$(resolve_nas_host)"
    ui_url="http://${nas_host}:${NAS_DIFF_FRONTEND_PORT:-15173}"

    sed -i.bak "s#__NAS_DIFF_UI_URL__#${ui_url}#g" "${UI_CONFIG_TEMPLATE}"
    rm -f "${UI_CONFIG_TEMPLATE}.bak"
    log "Rendered DSM launcher config with UI URL ${ui_url}"
}

render_ui_config
