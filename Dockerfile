FROM node:16 AS compile-frontend

COPY . /src

WORKDIR /src/src-ui
RUN npm update npm -g && npm install
RUN ./node_modules/.bin/ng build --configuration production


FROM ubuntu:20.04 AS jbig2enc

WORKDIR /usr/src/jbig2enc

RUN apt-get update && apt-get install -y --no-install-recommends build-essential automake libtool libleptonica-dev zlib1g-dev git ca-certificates

RUN git clone https://github.com/agl/jbig2enc .
RUN ./autogen.sh
RUN ./configure && make


FROM python:3.9-slim-bullseye

# Binary dependencies
RUN apt-get update \
	&& apt-get -y --no-install-recommends install \
  	# Basic dependencies
		curl \
		gnupg \
		imagemagick \
		gettext \
		tzdata \
		gosu \
		# fonts for text file thumbnail generation
		fonts-liberation \
		# for Numpy
		libatlas-base-dev \
		libxslt1-dev \
		# thumbnail size reduction
		optipng \
		libxml2 \
		pngquant \
		unpaper \
		zlib1g \
		ghostscript \
		icc-profiles-free \
  	# Mime type detection
		file \
		libmagic-dev \
		media-types \
		# OCRmyPDF dependencies
		liblept5 \
		tesseract-ocr \
		tesseract-ocr-eng \
		tesseract-ocr-deu \
		tesseract-ocr-fra \
		tesseract-ocr-ita \
		tesseract-ocr-spa \
  && rm -rf /var/lib/apt/lists/*

# copy jbig2enc
COPY --from=jbig2enc /usr/src/jbig2enc/src/.libs/libjbig2enc* /usr/local/lib/
COPY --from=jbig2enc /usr/src/jbig2enc/src/jbig2 /usr/local/bin/
COPY --from=jbig2enc /usr/src/jbig2enc/src/*.h /usr/local/include/

WORKDIR /usr/src/paperless/src/

COPY requirements.txt ../

# Python dependencies
RUN apt-get update \
  && apt-get -y --no-install-recommends install \
		build-essential \
		libpq-dev \
		git \
		zlib1g-dev \
		libjpeg62-turbo-dev \
	&& if [ "$(uname -m)" = "armv7l" ] || [ "$(uname -m)" = "aarch64" ]; \
	  then echo "Building qpdf" \
	  && mkdir -p /usr/src/qpdf \
	  && cd /usr/src/qpdf \
	  && git clone https://github.com/qpdf/qpdf.git . \
	  && git checkout --quiet release-qpdf-10.6.2 \
	  && ./configure \
	  && make \
	  && make install \
	  && cd /usr/src/paperless/src/ \
	  && rm -rf /usr/src/qpdf; \
	else \
	  echo "Skipping qpdf build because pikepdf binary wheels are available."; \
	fi \
    && python3 -m pip install --upgrade pip wheel \
	&& python3 -m pip install --default-timeout=1000 --upgrade --no-cache-dir supervisor \
  	&& python3 -m pip install --default-timeout=1000 --no-cache-dir -r ../requirements.txt \
	&& apt-get -y purge build-essential git zlib1g-dev libjpeg62-turbo-dev \
	&& apt-get -y autoremove --purge \
	&& rm -rf /var/lib/apt/lists/*

# setup docker-specific things
COPY docker/ ./docker/

RUN cd docker \
  	&& cp imagemagick-policy.xml /etc/ImageMagick-6/policy.xml \
	&& mkdir /var/log/supervisord /var/run/supervisord \
	&& cp supervisord.conf /etc/supervisord.conf \
	&& cp docker-entrypoint.sh /sbin/docker-entrypoint.sh \
	&& cp docker-prepare.sh /sbin/docker-prepare.sh \
	&& chmod 755 /sbin/docker-entrypoint.sh \
	&& chmod +x install_management_commands.sh \
	&& ./install_management_commands.sh \
	&& cd .. \
	&& rm docker -rf

COPY gunicorn.conf.py ../

# copy app
COPY --from=compile-frontend /src/src/ ./

# add users, setup scripts
RUN addgroup --gid 1000 paperless \
	&& useradd --uid 1000 --gid paperless --home-dir /usr/src/paperless paperless \
	&& chown -R paperless:paperless ../ \
	&& gosu paperless python3 manage.py collectstatic --clear --no-input \
	&& gosu paperless python3 manage.py compilemessages

VOLUME ["/usr/src/paperless/data", "/usr/src/paperless/media", "/usr/src/paperless/consume", "/usr/src/paperless/export"]
ENTRYPOINT ["/sbin/docker-entrypoint.sh"]
EXPOSE 8000
CMD ["/usr/local/bin/supervisord", "-c", "/etc/supervisord.conf"]

LABEL org.opencontainers.image.authors="paperless-ngx team <hello@paperless-ngx.com>"
LABEL org.opencontainers.image.documentation="https://paperless-ngx.readthedocs.io/en/latest/"
LABEL org.opencontainers.image.source="https://github.com/paperless-ngx/paperless-ngx"
LABEL org.opencontainers.image.url="https://github.com/paperless-ngx/paperless-ngx"
LABEL org.opencontainers.image.licenses="GPL-3.0-only"
