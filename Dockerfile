FROM ubuntu:20.04 AS jbig2enc

WORKDIR /usr/src/jbig2enc

RUN apt-get update && apt-get install -y --no-install-recommends build-essential automake libtool libleptonica-dev zlib1g-dev git ca-certificates

RUN git clone https://github.com/agl/jbig2enc .
RUN ./autogen.sh
RUN ./configure && make

FROM python:3.7-slim

WORKDIR /usr/src/paperless/

COPY requirements.txt ./

# Binary dependencies
RUN apt-get update \
  && apt-get -y --no-install-recommends install \
  	# Basic dependencies
		curl \
		file \
		fonts-liberation \
		gettext \
		gnupg \
		imagemagick \
		libxslt1-dev \
		mime-support \
		optipng \
		sudo \
		tzdata \
  	# OCRmyPDF dependencies
		ghostscript \
		icc-profiles-free \
		liblept5 \
		libxml2 \
		pngquant \
		qpdf \
		tesseract-ocr \
		tesseract-ocr-eng \
		tesseract-ocr-deu \
		tesseract-ocr-fra \
		tesseract-ocr-ita \
		tesseract-ocr-spa \
		unpaper \
		zlib1g \
		&& rm -rf /var/lib/apt/lists/*

# This pulls in updated dependencies from bullseye to fix some issues with file type detection.
# TODO: Remove this once bullseye releases.
RUN echo "deb http://deb.debian.org/debian bullseye main" > /etc/apt/sources.list.d/bullseye.list \
  && apt-get update \
  && apt-get install --no-install-recommends -y file libmagic-dev \
  && rm -rf /var/lib/apt/lists/* \
  && rm /etc/apt/sources.list.d/bullseye.list

# Python dependencies
RUN apt-get update \
  && apt-get -y --no-install-recommends install \
		build-essential \
		libatlas-base-dev \
		libpoppler-cpp-dev \
		libpq-dev \
		libqpdf-dev \
	&& python3 -m pip install --upgrade --no-cache-dir supervisor \
  && python3 -m pip install --no-cache-dir -r requirements.txt \
	&& apt-get -y purge build-essential libqpdf-dev \
	&& apt-get -y autoremove --purge \
	&& rm -rf /var/lib/apt/lists/* \
	&& mkdir /var/log/supervisord /var/run/supervisord


# copy scripts
# this fixes issues with imagemagick and PDF
COPY docker/imagemagick-policy.xml /etc/ImageMagick-6/policy.xml
COPY docker/gunicorn.conf.py ./
COPY docker/supervisord.conf /etc/supervisord.conf
COPY docker/docker-entrypoint.sh /sbin/docker-entrypoint.sh

# copy jbig2enc
COPY --from=jbig2enc /usr/src/jbig2enc/src/.libs/libjbig2enc* /usr/local/lib/
COPY --from=jbig2enc /usr/src/jbig2enc/src/jbig2 /usr/local/bin/
COPY --from=jbig2enc /usr/src/jbig2enc/src/*.h /usr/local/include/


# copy app
COPY src/ ./src/

# add users, setup scripts
RUN addgroup --gid 1000 paperless \
	&& useradd --uid 1000 --gid paperless --home-dir /usr/src/paperless paperless \
	&& chown -R paperless:paperless . \
	&& chmod 755 /sbin/docker-entrypoint.sh

WORKDIR /usr/src/paperless/src/

RUN sudo -HEu paperless python3 manage.py collectstatic --clear --no-input

RUN sudo -HEu paperless python3 manage.py compilemessages

VOLUME ["/usr/src/paperless/data", "/usr/src/paperless/media", "/usr/src/paperless/consume", "/usr/src/paperless/export"]
ENTRYPOINT ["/sbin/docker-entrypoint.sh"]
EXPOSE 8000
CMD ["/usr/local/bin/supervisord", "-c", "/etc/supervisord.conf"]

LABEL maintainer="Jonas Winkler <dev@jpwinkler.de>"
