# syntax=docker/dockerfile:1
# https://github.com/moby/buildkit/blob/master/frontend/dockerfile/docs/reference.md

# Stage: compile-frontend
# Purpose: Compiles the frontend
# Notes:
#  - Does NPM stuff with Typescript and such
FROM --platform=$BUILDPLATFORM docker.io/node:20-bookworm-slim AS compile-frontend

COPY ./src-ui /src/src-ui

WORKDIR /src/src-ui
RUN set -eux \
  && npm update npm -g \
  && npm ci
RUN set -eux \
  && ./node_modules/.bin/ng build --configuration production

# Stage: pipenv-base
# Purpose: Generates a requirements.txt file for building
# Comments:
#  - pipenv dependencies are not left in the final image
#  - pipenv can't touch the final image somehow
FROM --platform=$BUILDPLATFORM docker.io/python:3.11-alpine as pipenv-base

WORKDIR /usr/src/pipenv

COPY Pipfile* ./

RUN set -eux \
  && echo "Installing pipenv" \
    && python3 -m pip install --no-cache-dir --upgrade pipenv==2023.12.1 \
  && echo "Generating requirement.txt" \
    && pipenv requirements > requirements.txt

# Stage: main-app
# Purpose: The final image
# Comments:
#  - Don't leave anything extra in here
FROM docker.io/python:3.11-slim-bookworm as main-app

#LABEL org.opencontainers.image.authors="paperless-ngx team <hello@paperless-ngx.com>"
#LABEL org.opencontainers.image.documentation="https://docs.paperless-ngx.com/"
#LABEL org.opencontainers.image.source="https://github.com/paperless-ngx/paperless-ngx"
#LABEL org.opencontainers.image.url="https://github.com/paperless-ngx/paperless-ngx"
#LABEL org.opencontainers.image.licenses="GPL-3.0-only"

ARG DEBIAN_FRONTEND=noninteractive

# Buildx provided, must be defined to use though
ARG TARGETARCH

# Can be workflow provided, defaults set for manual building
ARG JBIG2ENC_VERSION=0.29
ARG QPDF_VERSION=11.6.4
ARG GS_VERSION=10.02.1

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Ignore warning from Whitenoise
    PYTHONWARNINGS="ignore:::django.http.response:517" \
    PNGX_CONTAINERIZED=1

#
# Begin installation and configuration
# Order the steps below from least often changed to most
#

# Packages need for running
ARG RUNTIME_PACKAGES="\
  # General utils
  curl \
  # Docker specific
  gosu \
  # Timezones support
  tzdata \
  # fonts for text file thumbnail generation
  fonts-liberation \
  gettext \
  ghostscript \
  gnupg \
  icc-profiles-free \
  imagemagick \
  # PostgreSQL
  libpq5 \
  postgresql-client \
  # MySQL / MariaDB
  mariadb-client \
  # OCRmyPDF dependencies
  tesseract-ocr \
  tesseract-ocr-vie \
  tesseract-ocr-eng \
  unpaper \
  pngquant \
  jbig2dec \
  # lxml
  libxml2 \
  libxslt1.1 \
  # itself
  qpdf \
  # Mime type detection
  file \
  libmagic1 \
  media-types \
  zlib1g \
  # Barcode splitter
  libzbar0 \
  poppler-utils"

# Install basic runtime packages.
# These change very infrequently
RUN set -eux \
  echo "Installing system packages" \
    && apt-get update \
    && apt-get install --yes --quiet --no-install-recommends ${RUNTIME_PACKAGES} \
    && echo "Installing pre-built updates" \
      && echo "Installing qpdf ${QPDF_VERSION}" \
        && curl --fail --silent --show-error --location \
          --output libqpdf29_${QPDF_VERSION}-1_${TARGETARCH}.deb \
          https://github.com/tienthienhd/tc-edoc/releases/download/qpdf-${QPDF_VERSION}/libqpdf29_${QPDF_VERSION}-1_${TARGETARCH}.deb \
        && curl --fail --silent --show-error --location \
          --output qpdf_${QPDF_VERSION}-1_${TARGETARCH}.deb \
          https://github.com/tienthienhd/tc-edoc/releases/download/qpdf-${QPDF_VERSION}/qpdf_${QPDF_VERSION}-1_${TARGETARCH}.deb \
        && dpkg --install ./libqpdf29_${QPDF_VERSION}-1_${TARGETARCH}.deb \
        && dpkg --install ./qpdf_${QPDF_VERSION}-1_${TARGETARCH}.deb \
      && echo "Installing Ghostscript ${GS_VERSION}" \
        && curl --fail --silent --show-error --location \
          --output libgs10_${GS_VERSION}.dfsg-2_${TARGETARCH}.deb \
          https://github.com/tienthienhd/tc-edoc/releases/download/ghostscript-${GS_VERSION}/libgs10_${GS_VERSION}.dfsg-1_${TARGETARCH}.deb \
        && curl --fail --silent --show-error --location \
          --output ghostscript_${GS_VERSION}.dfsg-2_${TARGETARCH}.deb \
          https://github.com/tienthienhd/tc-edoc/releases/download/ghostscript-${GS_VERSION}/ghostscript_${GS_VERSION}.dfsg-1_${TARGETARCH}.deb \
        && curl --fail --silent --show-error --location \
          --output libgs10-common_${GS_VERSION}.dfsg-2_all.deb \
          https://github.com/tienthienhd/tc-edoc/releases/download/ghostscript-${GS_VERSION}/libgs10-common_${GS_VERSION}.dfsg-1_all.deb \
        && dpkg --install ./libgs10-common_${GS_VERSION}.dfsg-2_all.deb \
        && dpkg --install ./libgs10_${GS_VERSION}.dfsg-2_${TARGETARCH}.deb \
        && dpkg --install ./ghostscript_${GS_VERSION}.dfsg-2_${TARGETARCH}.deb \
      && echo "Installing jbig2enc" \
        && curl --fail --silent --show-error --location \
          --output jbig2enc_${JBIG2ENC_VERSION}-1_${TARGETARCH}.deb \
          https://github.com/tienthienhd/tc-edoc/releases/download/jbig2enc-${JBIG2ENC_VERSION}/jbig2enc_${JBIG2ENC_VERSION}-1_${TARGETARCH}.deb \
        && dpkg --install ./jbig2enc_${JBIG2ENC_VERSION}-1_${TARGETARCH}.deb \
      && echo "Cleaning up image layer" \
        && rm --force --verbose *.deb \
    && rm --recursive --force --verbose /var/lib/apt/lists/* \
  && echo "Installing supervisor" \
    && python3 -m pip install --default-timeout=1000 --upgrade --no-cache-dir supervisor==4.2.5

# Copy gunicorn config
# Changes very infrequently
WORKDIR /usr/src/edoc/

COPY gunicorn.conf.py .

# setup docker-specific things
# These change sometimes, but rarely
WORKDIR /usr/src/edoc/src/docker/

COPY [ \
  "docker/imagemagick-policy.xml", \
  "docker/supervisord.conf", \
  "docker/docker-entrypoint.sh", \
  "docker/docker-prepare.sh", \
  "docker/edoc_cmd.sh", \
  "docker/wait-for-redis.py", \
  "docker/env-from-file.sh", \
  "docker/management_script.sh", \
  "docker/flower-conditional.sh", \
  "docker/install_management_commands.sh", \
  "/usr/src/edoc/src/docker/" \
]

RUN set -eux \
  && echo "Configuring ImageMagick" \
    && mv imagemagick-policy.xml /etc/ImageMagick-6/policy.xml \
  && echo "Configuring supervisord" \
    && mkdir /var/log/supervisord /var/run/supervisord \
    && mv supervisord.conf /etc/supervisord.conf \
  && echo "Setting up Docker scripts" \
    && mv docker-entrypoint.sh /sbin/docker-entrypoint.sh \
    && chmod 755 /sbin/docker-entrypoint.sh \
    && mv docker-prepare.sh /sbin/docker-prepare.sh \
    && chmod 755 /sbin/docker-prepare.sh \
    && mv wait-for-redis.py /sbin/wait-for-redis.py \
    && chmod 755 /sbin/wait-for-redis.py \
    && mv env-from-file.sh /sbin/env-from-file.sh \
    && chmod 755 /sbin/env-from-file.sh \
    && mv edoc_cmd.sh /usr/local/bin/edoc_cmd.sh \
    && chmod 755 /usr/local/bin/edoc_cmd.sh \
    && mv flower-conditional.sh /usr/local/bin/flower-conditional.sh \
    && chmod 755 /usr/local/bin/flower-conditional.sh \
  && echo "Installing management commands" \
    && chmod +x install_management_commands.sh \
    && ./install_management_commands.sh

WORKDIR /usr/src/edoc/src/

# Python dependencies
# Change pretty frequently
COPY --from=pipenv-base /usr/src/pipenv/requirements.txt ./

# Packages needed only for building a few quick Python
# dependencies
ARG BUILD_PACKAGES="\

  build-essential \
  git \
  # https://www.psycopg.org/docs/install.html#prerequisites
  libpq-dev \
  # https://github.com/PyMySQL/mysqlclient#linux
  default-libmysqlclient-dev \
  pkg-config"

# hadolint ignore=DL3042
RUN --mount=type=cache,target=/root/.cache/pip/,id=pip-cache \
  set -eux \
  && echo "Installing build system packages" \
    && apt-get update \
    && apt-get install --yes --quiet --no-install-recommends ${BUILD_PACKAGES} \
    && python3 -m pip install --no-cache-dir --upgrade setuptools wheel \
  && echo "Installing Python requirements" \
    && python3 -m pip install --default-timeout=1000 --no-cache-dir --requirement requirements.txt \
  && echo "Installing NLTK data" \
    && python3 -W ignore::RuntimeWarning -m nltk.downloader -d "/usr/share/nltk_data" snowball_data \
    && python3 -W ignore::RuntimeWarning -m nltk.downloader -d "/usr/share/nltk_data" stopwords \
    && python3 -W ignore::RuntimeWarning -m nltk.downloader -d "/usr/share/nltk_data" punkt \
  && echo "Cleaning up image" \
    && apt-get --yes purge ${BUILD_PACKAGES} \
    && apt-get --yes autoremove --purge \
    && apt-get clean --yes \
    && rm --recursive --force --verbose /var/lib/apt/lists/* \
    && rm --recursive --force --verbose /tmp/* \
    && rm --recursive --force --verbose /var/tmp/* \
    && rm --recursive --force --verbose /var/cache/apt/archives/* \
    && truncate --size 0 /var/log/*log

# copy backend
COPY --chown=1000:1000 ./src ./

# copy frontend
COPY --from=compile-frontend --chown=1000:1000 /src/src/documents/static/frontend/ ./documents/static/frontend/

# add users, setup scripts
# Mount the compiled frontend to expected location
RUN set -eux \
  && echo "Setting up user/group" \
    && addgroup --gid 1000 edoc \
    && useradd --uid 1000 --gid edoc --home-dir /usr/src/edoc edoc \
  && echo "Creating volume directories" \
    && mkdir --parents --verbose /usr/src/edoc/data \
    && mkdir --parents --verbose /usr/src/edoc/media \
    && mkdir --parents --verbose /usr/src/edoc/consume \
    && mkdir --parents --verbose /usr/src/edoc/export \
  && echo "Adjusting all permissions" \
    && chown --from root:root --changes --recursive edoc:edoc /usr/src/edoc \
  && echo "Collecting static files" \
    && gosu edoc python3 manage.py collectstatic --clear --no-input --link \
    && gosu edoc python3 manage.py compilemessages

VOLUME ["/usr/src/edoc/data", \
        "/usr/src/edoc/media", \
        "/usr/src/edoc/consume", \
        "/usr/src/edoc/export"]

ENTRYPOINT ["/sbin/docker-entrypoint.sh"]

EXPOSE 8000

CMD ["/usr/local/bin/edoc_cmd.sh"]

HEALTHCHECK --interval=30s --timeout=10s --retries=5 CMD [ "curl", "-fs", "-S", "--max-time", "2", "http://localhost:8000" ]
