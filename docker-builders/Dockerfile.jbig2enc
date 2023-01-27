# This Dockerfile compiles the jbig2enc library
# Inputs:
#    - JBIG2ENC_VERSION - the Git tag to checkout and build

FROM debian:bullseye-slim as main

LABEL org.opencontainers.image.description="A intermediate image with jbig2enc built"

ARG DEBIAN_FRONTEND=noninteractive
ARG JBIG2ENC_VERSION

ARG BUILD_PACKAGES="\
  build-essential \
  automake \
  libtool \
  libleptonica-dev \
  zlib1g-dev \
  git \
  ca-certificates"

WORKDIR /usr/src/jbig2enc

RUN set -eux \
  && echo "Installing build tools" \
    && apt-get update --quiet \
    && apt-get install --yes --quiet --no-install-recommends ${BUILD_PACKAGES} \
  && echo "Building jbig2enc" \
    && git clone --quiet --branch $JBIG2ENC_VERSION https://github.com/agl/jbig2enc . \
    && ./autogen.sh \
    && ./configure \
    && make \
  && echo "Gathering package data" \
    && dpkg-query -f '${Package;-40}${Version}\n' -W > ./pkg-list.txt \
  && echo "Cleaning up image" \
    && apt-get -y purge ${BUILD_PACKAGES} \
    && apt-get -y autoremove --purge \
    && rm -rf /var/lib/apt/lists/* \
  && echo "Moving files around" \
    && mkdir build \
    # Unlink a symlink that causes problems
    && unlink ./src/.libs/libjbig2enc.la \
    # Move what the link pointed to
    && mv ./src/libjbig2enc.la ./build/ \
    # Move the shared library .so files
    && mv ./src/.libs/libjbig2enc* ./build/ \
    # And move the cli binary
    && mv ./src/jbig2 ./build/ \
    && mv ./pkg-list.txt ./build/
