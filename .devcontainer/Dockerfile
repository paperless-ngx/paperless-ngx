FROM ubuntu:22.10

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive && \
        apt-get -y install python3 python3-pip python3-dev imagemagick fonts-liberation gnupg \
        libpq-dev libmagic-dev mime-support libzbar0 poppler-utils unpaper ghostscript \
        icc-profiles-free qpdf liblept5 libxml2 pngquant zlib1g tesseract-ocr nodejs npm git pre-commit

RUN npm install -g @angular/cli

RUN pip3 install pipenv

# Comment this when it is used with docker compose
# RUN apt-get update && apt-get -y install redis



