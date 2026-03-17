#!/bin/bash

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/common.sh"

IMAGES_DIR="${PKG_TARGET}/images"

load_images() {
    local archive

    require_path "${IMAGES_DIR}"

    for archive in "${IMAGES_DIR}"/*.tar "${IMAGES_DIR}"/*.tar.gz; do
        [ -e "${archive}" ] || continue
        log "Loading image archive ${archive}"
        run_docker load -i "${archive}"
    done
}

load_images
