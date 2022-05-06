# Pull the installer images from the library
# These are all built previously
# They provide either a .deb or .whl

ARG JBIG2ENC_VERSION
ARG QPDF_VERSION
ARG PIKEPDF_VERSION
ARG PSYCOPG2_VERSION

FROM ghcr.io/paperless-ngx/paperless-ngx/builder/jbig2enc:${JBIG2ENC_VERSION} as jbig2enc-builder
FROM ghcr.io/paperless-ngx/paperless-ngx/builder/qpdf:${QPDF_VERSION} as qpdf-builder
FROM ghcr.io/paperless-ngx/paperless-ngx/builder/pikepdf:${PIKEPDF_VERSION} as pikepdf-builder
FROM ghcr.io/paperless-ngx/paperless-ngx/builder/psycopg2:${PSYCOPG2_VERSION} as psycopg2-builder

FROM --platform=$BUILDPLATFORM node:16-bullseye-slim AS compile-frontend

# This stage compiles the frontend
# This stage runs once for the native platform, as the outputs are not
# dependent on target arch
# Inputs: None

COPY ./src-ui /src/src-ui

WORKDIR /src/src-ui
RUN set -eux \
  && npm update npm -g \
  && npm ci --no-optional
RUN set -eux \
  && ./node_modules/.bin/ng build --configuration production

FROM python:3.9-slim-bullseye as main-app

LABEL org.opencontainers.image.authors="paperless-ngx team <hello@paperless-ngx.com>"
LABEL org.opencontainers.image.documentation="https://paperless-ngx.readthedocs.io/en/latest/"
LABEL org.opencontainers.image.source="https://github.com/paperless-ngx/paperless-ngx"
LABEL org.opencontainers.image.url="https://github.com/paperless-ngx/paperless-ngx"
LABEL org.opencontainers.image.licenses="GPL-3.0-only"

ARG DEBIAN_FRONTEND=noninteractive

# Packages needed only for building
ARG BUILD_PACKAGES="\
  build-essential \
  git \
  mariadb-client \
  python3-dev"

# Packages need for running
ARG RUNTIME_PACKAGES="\
  curl \
  file \
  # fonts for text file thumbnail generation
  default-libmysqlclient-dev \
  fonts-liberation \
  gettext \
  ghostscript \
  gnupg \
  gosu \
  icc-profiles-free \
  imagemagick \
  media-types \
  liblept5 \
  libpq5 \
  libxml2 \
  liblcms2-2 \
  libtiff5 \
  libxslt1.1 \
  libfreetype6 \
  libwebp6 \
  libopenjp2-7 \
  libimagequant0 \
  libraqm0 \
  libgnutls30 \
  libjpeg62-turbo \
  optipng \
  python3 \
  python3-pip \
  python3-setuptools \
  postgresql-client \
  # For Numpy
  libatlas3-base \
  # thumbnail size reduction
  pngquant \
  # OCRmyPDF dependencies
  tesseract-ocr \
  tesseract-ocr-eng \
  tesseract-ocr-deu \
  tesseract-ocr-fra \
  tesseract-ocr-ita \
  tesseract-ocr-spa \
  tzdata \
  unpaper \
  # Mime type detection
  zlib1g \
  # Barcode splitter
  libzbar0 \
  poppler-utils"

WORKDIR /usr/src/paperless/src/

# Copy qpdf and runtime library
COPY --from=qpdf-builder /usr/src/qpdf/libqpdf28_*.deb ./
COPY --from=qpdf-builder /usr/src/qpdf/qpdf_*.deb ./

# Copy pikepdf wheel and dependencies
COPY --from=pikepdf-builder /usr/src/pikepdf/wheels/*.whl ./

# Copy psycopg2 wheel
COPY --from=psycopg2-builder /usr/src/psycopg2/wheels/psycopg2*.whl ./

# copy jbig2enc
COPY --from=jbig2enc-builder /usr/src/jbig2enc/src/.libs/libjbig2enc* /usr/local/lib/
COPY --from=jbig2enc-builder /usr/src/jbig2enc/src/jbig2 /usr/local/bin/
COPY --from=jbig2enc-builder /usr/src/jbig2enc/src/*.h /usr/local/include/

COPY requirements.txt ../

# Python dependencies
RUN set -eux \
  && apt-get update \
  && apt-get install --yes --quiet --no-install-recommends ${RUNTIME_PACKAGES} ${BUILD_PACKAGES} \
  && python3 -m pip install --no-cache-dir --upgrade wheel \
  && echo "Installing qpdf" \
    && apt-get install --yes --no-install-recommends ./libqpdf28_*.deb \
    && apt-get install --yes --no-install-recommends ./qpdf_*.deb \
  && echo "Installing pikepdf and dependencies wheel" \
    && python3 -m pip install --no-cache-dir packaging*.whl \
    && python3 -m pip install --no-cache-dir lxml*.whl \
    && python3 -m pip install --no-cache-dir Pillow*.whl \
    && python3 -m pip install --no-cache-dir pyparsing*.whl \
    && python3 -m pip install --no-cache-dir pikepdf*.whl \
    && python -m pip list \
  && echo "Installing psycopg2 wheel" \
    && python3 -m pip install --no-cache-dir psycopg2*.whl \
    && python -m pip list \
  && echo "Installing supervisor" \
    && python3 -m pip install --default-timeout=1000 --upgrade --no-cache-dir supervisor \
  && echo "Installing Python requirements" \
    && python3 -m pip install --default-timeout=1000 --no-cache-dir -r ../requirements.txt \
  && echo "Cleaning up image" \
    && apt-get -y purge ${BUILD_PACKAGES} \
    && apt-get -y autoremove --purge \
    && apt-get clean --yes \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/* \
    && rm -rf /var/cache/apt/archives/* \
    && truncate -s 0 /var/log/*log

# setup docker-specific things
COPY docker/ ./docker/

WORKDIR /usr/src/paperless/src/docker/

RUN set -eux \
  && cp imagemagick-policy.xml /etc/ImageMagick-6/policy.xml \
  && mkdir /var/log/supervisord /var/run/supervisord \
  && cp supervisord.conf /etc/supervisord.conf \
  && cp docker-entrypoint.sh /sbin/docker-entrypoint.sh \
  && chmod 755 /sbin/docker-entrypoint.sh \
  && cp docker-prepare.sh /sbin/docker-prepare.sh \
  && chmod 755 /sbin/docker-prepare.sh \
  && cp wait-for-redis.py /sbin/wait-for-redis.py \
  && chmod 755 /sbin/wait-for-redis.py \
  && chmod +x install_management_commands.sh \
  && ./install_management_commands.sh

WORKDIR /usr/src/paperless/

COPY gunicorn.conf.py .

WORKDIR /usr/src/paperless/src/

# copy backend
COPY ./src ./

# copy frontend
COPY --from=compile-frontend /src/src/documents/static/frontend/ ./documents/static/frontend/

# add users, setup scripts
RUN set -eux \
  && addgroup --gid 1000 paperless \
  && useradd --uid 1000 --gid paperless --home-dir /usr/src/paperless paperless \
  && chown -R paperless:paperless ../ \
  && gosu paperless python3 manage.py collectstatic --clear --no-input \
  && gosu paperless python3 manage.py compilemessages

VOLUME ["/usr/src/paperless/data", \
        "/usr/src/paperless/media", \
        "/usr/src/paperless/consume", \
        "/usr/src/paperless/export"]

ENTRYPOINT ["/sbin/docker-entrypoint.sh"]

EXPOSE 8000

CMD ["/usr/local/bin/supervisord", "-c", "/etc/supervisord.conf"]
