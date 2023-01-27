# This Dockerfile builds the psycopg2 wheel
# Inputs:
#    - PSYCOPG2_VERSION - Version to build

#
# Stage: builder
# Purpose:
#  - Build the psycopg2 wheel
#
FROM python:3.9-slim-bullseye as builder

LABEL org.opencontainers.image.description="A intermediate image with psycopg2 wheel built"

ARG PSYCOPG2_VERSION
ARG DEBIAN_FRONTEND=noninteractive

ARG BUILD_PACKAGES="\
  build-essential \
  python3-dev \
  python3-pip \
  # https://www.psycopg.org/docs/install.html#prerequisites
  libpq-dev"

WORKDIR /usr/src

# As this is an base image for a multi-stage final image
# the added size of the install is basically irrelevant

RUN set -eux \
  && echo "Installing build tools" \
    && apt-get update --quiet \
    && apt-get install --yes --quiet --no-install-recommends ${BUILD_PACKAGES} \
  && echo "Installing Python tools" \
    && python3 -m pip install --no-cache-dir --upgrade pip wheel \
  && echo "Building psycopg2 wheel ${PSYCOPG2_VERSION}" \
    && cd /usr/src \
    && mkdir wheels \
    && python3 -m pip wheel \
      # Build the package at the required version
      psycopg2==${PSYCOPG2_VERSION} \
      # Output the *.whl into this directory
      --wheel-dir wheels \
      # Do not use a binary packge for the package being built
      --no-binary=psycopg2 \
      # Do use binary packages for dependencies
      --prefer-binary \
      # Don't cache build files
      --no-cache-dir \
    && ls -ahl wheels/ \
  && echo "Gathering package data" \
    && dpkg-query -f '${Package;-40}${Version}\n' -W > ./wheels/pkg-list.txt \
  && echo "Cleaning up image" \
    && apt-get -y purge ${BUILD_PACKAGES} \
    && apt-get -y autoremove --purge \
    && rm -rf /var/lib/apt/lists/*

#
# Stage: package
# Purpose: Holds the compiled .whl files in a tiny image to pull
#
FROM alpine:3.17 as package

WORKDIR /usr/src/wheels/

COPY --from=builder /usr/src/wheels/*.whl ./
COPY --from=builder /usr/src/wheels/pkg-list.txt ./
