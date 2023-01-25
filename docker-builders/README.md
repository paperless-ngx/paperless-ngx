# Installer Library

This folder contains the Dockerfiles for building certain installers or libraries, which are then pulled into the main image.

## [jbig2enc](https://github.com/agl/jbig2enc)

### Why

JBIG is an image coding which can achieve better compression of images for PDFs.

### What

The Docker image builds a shared library file and utility, which is copied into the correct location in the final image.

See Also:

- [OCRMyPDF Documentation](https://ocrmypdf.readthedocs.io/en/latest/jbig2.html)

## [psycopg2](https://www.psycopg.org/)

### Why

The pre-built wheels of psycopg2 are built on Debian 9, which provides a quite old version of libpq-dev. This causes issue with authentication methods.

### What

The image builds psycopg2 wheels on Debian 10 and places the produced wheels into `/usr/src/wheels/`.

See Also:

- [Issue 266](https://github.com/paperless-ngx/paperless-ngx/issues/266)

## [qpdf](https://qpdf.readthedocs.io/en/stable/index.html)

### Why

qpdf and it's library provide tools to read, manipulate and fix up PDFs. Version 11 is also required by `pikepdf` 6+ and Debian 9 does not provide above version 10.

### What

The Docker image cross compiles .deb installers for each supported architecture of the main image. The installers are placed in `/usr/src/qpdf/${QPDF_VERSION}/${TARGETARCH}${TARGETVARIANT}/`

## [pikepdf](https://pikepdf.readthedocs.io/en/latest/)

### Why

Required by OCRMyPdf, this is a general purpose library for PDF manipulation in Python via the qpdf libraries.

### What

The built wheels are placed into `/usr/src/wheels/`
