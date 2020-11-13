###############################################################################
### Front end                                                               ###
###############################################################################

FROM node:current AS frontend

WORKDIR /usr/src/paperless/src-ui/

COPY src-ui/package* ./
RUN npm install

COPY src-ui .
RUN node_modules/.bin/ng build --prod --output-hashing none --sourceMap=false --output-path dist/paperless-ui

###############################################################################
### Back end                                                                ###
###############################################################################

FROM ubuntu:20.04

WORKDIR /usr/src/paperless/

COPY Pipfile* ./

#Dependencies
RUN apt-get update \
  && DEBIAN_FRONTEND="noninteractive" apt-get -y --no-install-recommends install \
		build-essential \
		curl \
		ghostscript \
		gnupg \
		imagemagick \
		libmagic-dev \
		libpoppler-cpp-dev \
		libpq-dev \
		optipng \
		python3 \
		python3-dev \
		python3-pip \
		sudo \
		tesseract-ocr \
		tesseract-ocr-eng \
		tesseract-ocr-deu \
		tesseract-ocr-fra \
		tesseract-ocr-ita \
		tesseract-ocr-spa \
		tzdata \
		unpaper \
	&& pip3 install --upgrade pipenv supervisor setuptools \
	&& pipenv install --system --deploy \
	&& pipenv --clear \
	&& apt-get -y purge build-essential python3-pip python3-dev \
	&& apt-get -y autoremove --purge \
	&& rm -rf /var/lib/apt/lists/* \
	&& mkdir /var/log/supervisord /var/run/supervisord

# copy scripts
# this fixes issues with imagemagick and PDF
COPY scripts/imagemagick-policy.xml /etc/ImageMagick-6/policy.xml
COPY scripts/gunicorn.conf.py ./
COPY scripts/supervisord.conf /etc/supervisord.conf
COPY scripts/docker-entrypoint.sh /sbin/docker-entrypoint.sh

# copy app
COPY src/ ./src/
COPY --from=frontend /usr/src/paperless/src-ui/dist/paperless-ui/ ./src/documents/static/frontend/

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
