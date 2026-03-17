#!/bin/bash

set -eu

export PATH="/usr/local/bin:/var/packages/Docker/target/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

PKG_NAME="nas-diff"
PKG_TARGET="${SYNOPKG_PKGDEST:-/var/packages/${PKG_NAME}/target}"
PKG_BASE="${SYNOPKG_PKGBASE:-$(dirname "${PKG_TARGET}")}"
PKG_ETC="${PKG_BASE}/etc"
PKG_VAR="${PKG_BASE}/var"
PKG_TMP="${PKG_BASE}/tmp"

RUNTIME_ROOT="${PKG_TARGET}/runtime"
COMPOSE_FILE="${RUNTIME_ROOT}/compose/docker-compose.package.yml"
ENV_TEMPLATE="${RUNTIME_ROOT}/env/nas-diff.env.template"
TARGET_ENV_FILE="${RUNTIME_ROOT}/env/nas-diff.env"
PACKAGE_CONF="${PKG_ETC}/package.conf"
PACKAGE_CONF_EXAMPLE="${RUNTIME_ROOT}/env/package.conf.example"
RENDERED_ENV_DIR="${PKG_VAR}/rendered-env"
RENDERED_ENV_FILE="${RENDERED_ENV_DIR}/nas-diff.env"
CONFIG_DIR="${PKG_ETC}/config"
DATA_DIR="${PKG_VAR}/data"
REDIS_DIR="${PKG_VAR}/redis"
LOG_DIR="${PKG_VAR}/logs"
RUNTIME_DIR="${PKG_VAR}/runtime"

log() {
    printf '[nas-diff package] %s\n' "$*"
}

fail() {
    printf '[nas-diff package] ERROR: %s\n' "$*" >&2
    exit 1
}

require_path() {
    local path="$1"

    [ -e "${path}" ] || fail "Missing required path: ${path}"
}

resolve_docker_bin() {
    local candidate

    for candidate in \
        "${DOCKER_BIN:-}" \
        /usr/local/bin/docker \
        /var/packages/Docker/target/usr/bin/docker \
        /usr/bin/docker
    do
        [ -n "${candidate}" ] || continue
        [ -x "${candidate}" ] || continue
        printf '%s\n' "${candidate}"
        return 0
    done

    command -v docker 2>/dev/null || return 1
}

resolve_docker_compose_bin() {
    local candidate

    for candidate in \
        "${DOCKER_COMPOSE_BIN:-}" \
        /usr/local/bin/docker-compose \
        /var/packages/Docker/target/usr/bin/docker-compose \
        /usr/bin/docker-compose
    do
        [ -n "${candidate}" ] || continue
        [ -x "${candidate}" ] || continue
        printf '%s\n' "${candidate}"
        return 0
    done

    command -v docker-compose 2>/dev/null || return 1
}

run_docker() {
    local docker_bin

    docker_bin="$(resolve_docker_bin)" || fail "Docker binary not found"
    "${docker_bin}" "$@"
}

ensure_package_dirs() {
    mkdir -p \
        "${PKG_ETC}" \
        "${PKG_VAR}" \
        "${PKG_TMP}" \
        "${CONFIG_DIR}" \
        "${DATA_DIR}" \
        "${REDIS_DIR}" \
        "${LOG_DIR}" \
        "${RUNTIME_DIR}" \
        "${RENDERED_ENV_DIR}"
}

ensure_package_config() {
    ensure_package_dirs

    if [ ! -f "${PACKAGE_CONF}" ] && [ -f "${PACKAGE_CONF_EXAMPLE}" ]; then
        cp -a "${PACKAGE_CONF_EXAMPLE}" "${PACKAGE_CONF}"
        chmod 600 "${PACKAGE_CONF}"
        log "Created default package config at ${PACKAGE_CONF}"
    fi
}

load_package_config() {
    if [ -f "${PACKAGE_CONF}" ]; then
        # shellcheck disable=SC1090
        . "${PACKAGE_CONF}"
    fi
}

run_compose() {
    local docker_bin compose_bin

    ensure_package_config
    load_package_config
    require_path "${COMPOSE_FILE}"
    require_path "${RENDERED_ENV_FILE}"

    docker_bin="$(resolve_docker_bin || true)"
    if [ -n "${docker_bin}" ] && "${docker_bin}" compose version >/dev/null 2>&1; then
        "${docker_bin}" compose -f "${COMPOSE_FILE}" --env-file "${RENDERED_ENV_FILE}" "$@"
        return 0
    fi

    compose_bin="$(resolve_docker_compose_bin)" || fail "Neither docker compose nor docker-compose is available"
    "${compose_bin}" -f "${COMPOSE_FILE}" --env-file "${RENDERED_ENV_FILE}" "$@"
}

resolve_nas_host() {
    load_package_config

    if [ -n "${NAS_DIFF_NAS_HOST:-}" ]; then
        printf '%s\n' "${NAS_DIFF_NAS_HOST}"
        return 0
    fi

    hostname -f 2>/dev/null || hostname
}
