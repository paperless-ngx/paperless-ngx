FROM alpine:3.7
WORKDIR /usr/src/paperless
COPY requirements.txt /usr/src/paperless/
# Copy application
COPY src/ /usr/src/paperless/src/
COPY data/ /usr/src/paperless/data/
COPY media/ /usr/src/paperless/media/
# Set export directory
ENV PAPERLESS_EXPORT_DIR /export
# Set consumption directory
ENV PAPERLESS_CONSUMPTION_DIR /consume
COPY scripts/docker-entrypoint.sh /sbin/docker-entrypoint.sh
# Install dependencies
RUN apk --no-cache --update add \
        python3 gnupg libmagic bash \
        sudo tesseract-ocr imagemagick ghostscript unpaper && \
    apk --no-cache add --virtual .build-dependencies \
        python3-dev gcc musl-dev zlib-dev jpeg-dev && \
## Install python dependencies
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    mkdir -p /usr/src/paperless && \
    pip3 install --no-cache-dir -r requirements.txt && \
# Remove build dependencies
    apk del .build-dependencies && \
# Create the consumption directory
    mkdir -p $PAPERLESS_CONSUMPTION_DIR && \
# Migrate database
    ./src/manage.py migrate && \
# Create user
    addgroup -g 1000 paperless && \
    adduser -D -u 1000 -G paperless -h /usr/src/paperless paperless && \
    chown -Rh paperless:paperless /usr/src/paperless && \
    mkdir -p $PAPERLESS_EXPORT_DIR && \
# Setup entrypoint
    chmod 755 /sbin/docker-entrypoint.sh
WORKDIR /usr/src/paperless/src
# Mount volumes
VOLUME ["/usr/src/paperless/data", "/usr/src/paperless/media", "/consume", "/export"]
ENTRYPOINT ["/sbin/docker-entrypoint.sh"]
CMD ["--help"]
