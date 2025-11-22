# Bare metal setup

## Requirements

OS: Linux

If you are using Windows, just build the Backend in WSL and the Frontend locally

## Installation

Install and setup Redis, and install the following packages:

```bash
$ sudo apt-get install build-essential python3-setuptools python3-wheel
$ sudo apt-get install python3 python3-pip python3-dev imagemagick fonts-liberation gnupg libpq-dev default-libmysqlclient-dev pkg-config libmagic-dev libzbar0 poppler-utils
$ sudo apt-get install unpaper ghostscript icc-profiles-free qpdf liblept5 libxml2 pngquant zlib1g tesseract-ocr
```

## Frontend

### Installation

```
cd src-ui
pnpm install -g @angular/cli
pnpm install
```

Development server:

```
ng serve
```

### Build

```
cd src-ui
ng build --configuration production
```

## Backend

### Setup

Copy `paperless.conf.example` to `paperless.conf` and enable debug mode within the
file via `PAPERLESS_DEBUG=true`.

Create consume and media directories:

```bash
$ mkdir -p consume media
$ uv sync --group dev
$ uv run pre-commit install
```

Apply migrations and create a superuser (also can be done via the web UI) for
your development instance:

```bash
$ cd src
$ uv run manage.py migrate
$ uv run manage.py createsuperuser
```

### Run

```bash
$ cd src
$ source ../.venv/bin/activate
$ python manage.py runserver & python manage.py document_consumer & celery --app paperless worker -l DEBUG
```

Development server:

```
ng serve
```

### Build

```
cd src-ui
ng build --configuration production
```

## Helpful links

[Development installation](https://docs.paperless-ngx.com/development/)

[Setup](https://docs.paperless-ngx.com/setup/#bare_metal)
