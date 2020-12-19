FROM python:3.7-slim

WORKDIR /usr/src/paperless/

COPY requirements.txt ./

#Dependencies
RUN apt-get update \
  && apt-get -y --no-install-recommends install \
		build-essential \
		curl \
		ghostscript \
		gnupg \
		icc-profiles-free \
		imagemagick \
		libatlas-base-dev \
		liblept5 \
		libmagic-dev \
		libpoppler-cpp-dev \
		libpq-dev \
		libqpdf-dev \
		libxml2 \
		optipng \
		pngquant \
		qpdf \
		sudo \
		tesseract-ocr \
		tesseract-ocr-eng \
		tesseract-ocr-deu \
		tesseract-ocr-fra \
		tesseract-ocr-ita \
		tesseract-ocr-spa \
		tzdata \
		unpaper \
		zlib1g \
	&& pip3 install --upgrade supervisor setuptools \
	&& pip install --no-cache-dir -r requirements.txt \
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

# copy app
COPY src/ ./src/

# add users, setup scripts
RUN addgroup --gid 1000 paperless \
	&& useradd --uid 1000 --gid paperless --home-dir /usr/src/paperless paperless \
	&& chown -R paperless:paperless . \
	&& chmod 755 /sbin/docker-entrypoint.sh

WORKDIR /usr/src/paperless/src/

RUN sudo -HEu paperless python3 manage.py collectstatic --clear --no-input

VOLUME ["/usr/src/paperless/data", "/usr/src/paperless/media", "/usr/src/paperless/consume", "/usr/src/paperless/export"]
ENTRYPOINT ["/sbin/docker-entrypoint.sh"]
CMD ["/usr/local/bin/supervisord", "-c", "/etc/supervisord.conf"]

LABEL maintainer="Jonas Winkler <dev@jpwinkler.de>"
