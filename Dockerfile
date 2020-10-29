###############################################################################
### Front end                                                               ###
###############################################################################

FROM node:current AS frontend

WORKDIR /usr/src/paperless/src-ui/

COPY src-ui/package* ./
RUN npm install

COPY src-ui .
RUN node_modules/.bin/ng build --prod --output-hashing none

###############################################################################
### Back end                                                                ###
###############################################################################

FROM python:3.8-slim

WORKDIR /usr/src/paperless/

COPY Pipfile* ./

#Dependencies
RUN apt-get update \
	&& apt-get -y --no-install-recommends install \
		build-essential \
		curl \
		ghostscript \
		gnupg \
		imagemagick \
		libmagic-dev \
		libpoppler-cpp-dev \
		libpq-dev \
		optipng \
		sudo \
		tesseract-ocr \
		tesseract-ocr-eng \
		tesseract-ocr-deu \
		tesseract-ocr-fra \
		tesseract-ocr-ita \
		tesseract-ocr-spa \
		tzdata \
		unpaper \
	&& pip install --upgrade pipenv \
	&& pipenv install --system --deploy \
	&& pipenv --clear \
	&& apt-get -y purge build-essential \
	&& apt-get -y autoremove --purge \
	&& rm -rf /var/lib/apt/lists/*

# # Copy application
COPY scripts/gunicorn.conf.py ./
COPY src/ ./src/
COPY --from=frontend /usr/src/paperless/src-ui/dist/paperless-ui/ ./src/documents/static/

RUN addgroup --gid 1000 paperless && \
	  useradd --uid 1000 --gid paperless --home-dir /usr/src/paperless paperless && \
	  chown -R paperless:paperless .

WORKDIR /usr/src/paperless/src/

RUN sudo -HEu paperless python3 manage.py collectstatic --clear --no-input

VOLUME ["/usr/src/paperless/data", "/usr/src/paperless/consume", "/usr/src/paperless/export"]

COPY scripts/docker-entrypoint.sh /sbin/docker-entrypoint.sh
RUN chmod 755 /sbin/docker-entrypoint.sh
ENTRYPOINT ["/sbin/docker-entrypoint.sh"]

CMD ["--help"]
