FROM node:16 AS compile-frontend

COPY . /src

WORKDIR /src/src-ui
RUN npm update npm -g && npm ci --no-optional
RUN ./node_modules/.bin/ng build --configuration production

FROM ghcr.io/paperless-ngx/builder/ngx-base:dev as main-app

LABEL org.opencontainers.image.authors="paperless-ngx team <hello@paperless-ngx.com>"
LABEL org.opencontainers.image.documentation="https://paperless-ngx.readthedocs.io/en/latest/"
LABEL org.opencontainers.image.source="https://github.com/paperless-ngx/paperless-ngx"
LABEL org.opencontainers.image.url="https://github.com/paperless-ngx/paperless-ngx"
LABEL org.opencontainers.image.licenses="GPL-3.0-only"

WORKDIR /usr/src/paperless/src/

COPY requirements.txt ../

# Python dependencies
RUN apt-get update \
  # python-Levenshtein still needs to be compiled here
  && apt-get -y --no-install-recommends install \
    build-essential \
    && python3 -m pip install --upgrade --no-cache-dir pip wheel \
  && python3 -m pip install --default-timeout=1000 --upgrade --no-cache-dir supervisor \
  && python3 -m pip install --default-timeout=1000 --no-cache-dir -r ../requirements.txt \
  && apt-get -y purge build-essential \
  && apt-get -y autoremove --purge \
  && rm -rf /var/lib/apt/lists/*

# setup docker-specific things
COPY docker/ ./docker/

RUN cd docker \
    && cp imagemagick-policy.xml /etc/ImageMagick-6/policy.xml \
  && mkdir /var/log/supervisord /var/run/supervisord \
  && cp supervisord.conf /etc/supervisord.conf \
  && cp docker-entrypoint.sh /sbin/docker-entrypoint.sh \
  && chmod 755 /sbin/docker-entrypoint.sh \
  && cp docker-prepare.sh /sbin/docker-prepare.sh \
  && chmod 755 /sbin/docker-prepare.sh \
  && chmod +x install_management_commands.sh \
  && ./install_management_commands.sh \
  && cd .. \
  && rm -rf docker/

COPY gunicorn.conf.py ../

# copy app
COPY --from=compile-frontend /src/src/ ./

# add users, setup scripts
RUN addgroup --gid 1000 paperless \
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
