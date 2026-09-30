FROM ghcr.io/home-assistant/base:latest

ARG BUILD_VERSION=0.1.4
ARG BUILD_ARCH=amd64

LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.title="Get HA Recipe Manager" \
      org.opencontainers.image.description="Installer for the HA Recipe Manager integration" \
      org.opencontainers.image.licenses="MIT"

RUN apk add --no-cache unzip

COPY run.sh /etc/addon/run
COPY ha_recipe_manager.zip /opt/ha_recipe_manager.zip
COPY ha_recipe_manager.zip.sha256 /opt/ha_recipe_manager.zip.sha256

RUN chmod a+x /etc/addon/run

CMD ["/etc/addon/run"]
