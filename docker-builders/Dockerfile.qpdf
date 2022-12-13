#
# Stage: pre-build
# Purpose:
#  - Installs common packages
#  - Sets common environment variables related to dpkg
#  - Aquires the qpdf source from bookwork
# Useful Links:
#  - https://qpdf.readthedocs.io/en/stable/installation.html#system-requirements
#  - https://wiki.debian.org/Multiarch/HOWTO
#  - https://wiki.debian.org/CrossCompiling
#

FROM debian:bullseye-slim as pre-build

ARG QPDF_VERSION

ARG COMMON_BUILD_PACKAGES="\
  cmake \
  debhelper\
  debian-keyring \
  devscripts \
  dpkg-dev \
  equivs \
  packaging-dev \
  libtool"

ENV DEB_BUILD_OPTIONS="terse nocheck nodoc parallel=2"

WORKDIR /usr/src

RUN set -eux \
  && echo "Installing common packages" \
    && apt-get update --quiet \
    && apt-get install --yes --quiet --no-install-recommends ${COMMON_BUILD_PACKAGES} \
  && echo "Getting qpdf source" \
    && echo "deb-src http://deb.debian.org/debian/ bookworm main" > /etc/apt/sources.list.d/bookworm-src.list \
    && apt-get update --quiet \
    && apt-get source --yes --quiet qpdf=${QPDF_VERSION}-1/bookworm

#
# Stage: amd64-builder
# Purpose: Builds qpdf for x86_64 (native build)
#
FROM pre-build as amd64-builder

ARG AMD64_BUILD_PACKAGES="\
  build-essential \
  libjpeg62-turbo-dev:amd64 \
  libgnutls28-dev:amd64 \
  zlib1g-dev:amd64"

WORKDIR /usr/src/qpdf-${QPDF_VERSION}

RUN set -eux \
  && echo "Beginning amd64" \
    && echo "Install amd64 packages" \
      && apt-get update --quiet \
      && apt-get install --yes --quiet --no-install-recommends ${AMD64_BUILD_PACKAGES} \
    && echo "Building amd64" \
      && dpkg-buildpackage --build=binary --unsigned-source --unsigned-changes --post-clean \
    && echo "Removing debug files" \
      && rm -f ../libqpdf29-dbgsym* \
      && rm -f ../qpdf-dbgsym* \
    && echo "Gathering package data" \
      && dpkg-query -f '${Package;-40}${Version}\n' -W > ../pkg-list.txt
#
# Stage: armhf-builder
# Purpose:
#  - Sets armhf specific environment
#  - Builds qpdf for armhf (cross compile)
#
FROM pre-build as armhf-builder

ARG ARMHF_PACKAGES="\
  crossbuild-essential-armhf \
  libjpeg62-turbo-dev:armhf \
  libgnutls28-dev:armhf \
  zlib1g-dev:armhf"

WORKDIR /usr/src/qpdf-${QPDF_VERSION}

ENV CXX="/usr/bin/arm-linux-gnueabihf-g++" \
    CC="/usr/bin/arm-linux-gnueabihf-gcc"

RUN set -eux \
  && echo "Beginning armhf" \
    && echo "Install armhf packages" \
      && dpkg --add-architecture armhf \
      && apt-get update --quiet \
      && apt-get install --yes --quiet --no-install-recommends ${ARMHF_PACKAGES} \
    && echo "Building armhf" \
      && dpkg-buildpackage --build=binary --unsigned-source --unsigned-changes --post-clean --host-arch armhf \
    && echo "Removing debug files" \
      && rm -f ../libqpdf29-dbgsym* \
      && rm -f ../qpdf-dbgsym* \
    && echo "Gathering package data" \
      && dpkg-query -f '${Package;-40}${Version}\n' -W > ../pkg-list.txt

#
# Stage: aarch64-builder
# Purpose:
#  - Sets aarch64 specific environment
#  - Builds qpdf for aarch64 (cross compile)
#
FROM pre-build as aarch64-builder

ARG ARM64_PACKAGES="\
  crossbuild-essential-arm64 \
  libjpeg62-turbo-dev:arm64 \
  libgnutls28-dev:arm64 \
  zlib1g-dev:arm64"

ENV CXX="/usr/bin/aarch64-linux-gnu-g++" \
    CC="/usr/bin/aarch64-linux-gnu-gcc"

WORKDIR /usr/src/qpdf-${QPDF_VERSION}

RUN set -eux \
  && echo "Beginning arm64" \
    && echo "Install arm64 packages" \
      && dpkg --add-architecture arm64 \
      && apt-get update --quiet \
      && apt-get install --yes --quiet --no-install-recommends ${ARM64_PACKAGES} \
    && echo "Building arm64" \
      && dpkg-buildpackage --build=binary --unsigned-source --unsigned-changes --post-clean --host-arch arm64 \
    && echo "Removing debug files" \
      && rm -f ../libqpdf29-dbgsym* \
      && rm -f ../qpdf-dbgsym* \
    && echo "Gathering package data" \
      && dpkg-query -f '${Package;-40}${Version}\n' -W > ../pkg-list.txt

#
# Stage: package
# Purpose: Holds the compiled .deb files in arch/variant specific folders
#
FROM alpine:3.17 as package

LABEL org.opencontainers.image.description="A image with qpdf installers stored in architecture & version specific folders"

ARG QPDF_VERSION

WORKDIR /usr/src/qpdf/${QPDF_VERSION}/amd64

COPY --from=amd64-builder /usr/src/*.deb ./
COPY --from=amd64-builder /usr/src/pkg-list.txt ./

# Note this is ${TARGETARCH}${TARGETVARIANT} for armv7
WORKDIR /usr/src/qpdf/${QPDF_VERSION}/armv7

COPY --from=armhf-builder /usr/src/*.deb ./
COPY --from=armhf-builder /usr/src/pkg-list.txt ./

WORKDIR /usr/src/qpdf/${QPDF_VERSION}/arm64

COPY --from=aarch64-builder /usr/src/*.deb ./
COPY --from=aarch64-builder /usr/src/pkg-list.txt ./
