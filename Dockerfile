FROM python:3.5.1
MAINTAINER Pit Kleyersburg <pitkley@googlemail.com>

# Install dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        sudo \
        tesseract-ocr tesseract-ocr-eng imagemagick ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
RUN mkdir -p /usr/src/paperless
WORKDIR /usr/src/paperless
COPY requirements.txt /usr/src/paperless/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
RUN mkdir -p /usr/src/paperless/src
COPY src/ /usr/src/paperless/src/

# Set consumption directory
ENV PAPERLESS_CONSUME /consume
RUN mkdir -p $PAPERLESS_CONSUME

# Migrate database
WORKDIR /usr/src/paperless/src
RUN mkdir /usr/src/paperless/data
RUN ./manage.py migrate

# Create user
RUN groupadd -g 1000 paperless \
    && useradd -u 1000 -g 1000 -d /usr/src/paperless paperless \
    && chown -Rh paperless:paperless /usr/src/paperless

# Setup entrypoint
COPY scripts/docker-entrypoint.sh /sbin/docker-entrypoint.sh
RUN chmod 755 /sbin/docker-entrypoint.sh

# Mount volumes
VOLUME ["/usr/src/paperless/data", "/usr/src/paperless/media", "/consume"]

ENTRYPOINT ["/sbin/docker-entrypoint.sh"]
CMD ["--help"]
