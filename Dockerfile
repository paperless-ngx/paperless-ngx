FROM alpine:latest

# Install dependencies
RUN apk --no-cache --update add \
        python3 python3-dev gcc musl-dev gnupg zlib-dev jpeg-dev libmagic \
        sudo tesseract-ocr imagemagick ghostscript unpaper

## Install python dependencies
RUN python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    mkdir -p /usr/src/paperless
WORKDIR /usr/src/paperless
COPY requirements.txt /usr/src/paperless/
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application
RUN mkdir -p /usr/src/paperless/src
RUN mkdir -p /usr/src/paperless/data
RUN mkdir -p /usr/src/paperless/media
COPY src/ /usr/src/paperless/src/
COPY data/ /usr/src/paperless/data/
COPY media/ /usr/src/paperless/media/

# Set consumption directory
ENV PAPERLESS_CONSUMPTION_DIR /consume
RUN mkdir -p $PAPERLESS_CONSUMPTION_DIR

# Migrate database
WORKDIR /usr/src/paperless/src
RUN ./manage.py migrate

# Create user
RUN addgroup -g 1000 paperless \
    && adduser -D -u 1000 -G paperless -h /usr/src/paperless paperless \
    && chown -Rh paperless:paperless /usr/src/paperless

# Set export directory
ENV PAPERLESS_EXPORT_DIR /export
RUN mkdir -p $PAPERLESS_EXPORT_DIR

# Setup entrypoint
COPY scripts/docker-entrypoint.sh /sbin/docker-entrypoint.sh
RUN chmod 755 /sbin/docker-entrypoint.sh

# Mount volumes
VOLUME ["/usr/src/paperless/data", "/usr/src/paperless/media", "/consume", "/export"]

ENTRYPOINT ["/sbin/docker-entrypoint.sh"]
CMD ["--help"]
