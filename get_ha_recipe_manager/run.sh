#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

set -Eeuo pipefail

readonly INTEGRATION="ha_recipe_manager"
readonly CONFIG_ROOT="/homeassistant"
readonly COMPONENTS_ROOT="${CONFIG_ROOT}/custom_components"
readonly TARGET="${COMPONENTS_ROOT}/${INTEGRATION}"
readonly STAGING="${COMPONENTS_ROOT}/.${INTEGRATION}.new"
readonly BACKUP="${COMPONENTS_ROOT}/.${INTEGRATION}.previous"
readonly TEMP_ROOT="/tmp/ha-recipe-manager-install"
readonly PAYLOAD="/opt/ha_recipe_manager.zip"
readonly CHECKSUM="/opt/ha_recipe_manager.zip.sha256"

restore_previous() {
    local status="$1"

    trap - EXIT

    if [[ ${status} -ne 0 ]]; then
        bashio::log.error "Die Installation ist fehlgeschlagen."
        if [[ ! -e "${TARGET}" && -d "${BACKUP}" ]]; then
            mv "${BACKUP}" "${TARGET}"
            bashio::log.warning "Die vorherige Version wurde wiederhergestellt."
        fi
    fi

    rm -rf "${STAGING}" "${TEMP_ROOT}"
    exit "${status}"
}

trap 'restore_previous "$?"' EXIT

bashio::log.info "Pruefe Installationspaket..."
bashio::fs.directory_exists "${CONFIG_ROOT}" \
    || bashio::exit.nok "Das Home-Assistant-Konfigurationsverzeichnis ist nicht eingebunden."

(cd /opt && sha256sum --check "$(basename "${CHECKSUM}")")

mkdir -p "${COMPONENTS_ROOT}"

if [[ ! -e "${TARGET}" && -d "${BACKUP}" ]]; then
    bashio::log.warning "Stelle eine unterbrochene vorherige Installation wieder her."
    mv "${BACKUP}" "${TARGET}"
fi

rm -rf "${STAGING}" "${BACKUP}" "${TEMP_ROOT}"
mkdir -p "${TEMP_ROOT}"
unzip -q "${PAYLOAD}" -d "${TEMP_ROOT}"

readonly SOURCE="${TEMP_ROOT}/custom_components/${INTEGRATION}"
[[ -f "${SOURCE}/manifest.json" ]] \
    || bashio::exit.nok "Das Installationspaket enthaelt keine gueltige Integration."

cp -a "${SOURCE}" "${STAGING}"

if [[ -e "${TARGET}" ]]; then
    bashio::log.info "Aktualisiere die vorhandene Installation..."
    mv "${TARGET}" "${BACKUP}"
else
    bashio::log.info "Installiere HA Recipe Manager..."
fi

mv "${STAGING}" "${TARGET}"
rm -rf "${BACKUP}" "${TEMP_ROOT}"
trap - EXIT

bashio::log.info "HA Recipe Manager wurde erfolgreich installiert."
bashio::log.info "Starte Home Assistant neu und fuege danach die Integration unter Geraete & Dienste hinzu."
