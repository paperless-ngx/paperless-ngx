#!/usr/bin/env bash

# Example Usage: ./build-docker-imaage.sh -t paperless-ngx:my-awesome-feature

set -eux

# Parse what we can from Pipfile.lock
pikepdf_version=$(jq ".default.pikepdf.version" Pipfile.lock  | sed 's/=//g' | sed 's/"//g')
psycopg2_version=$(jq ".default.psycopg2.version" Pipfile.lock | sed 's/=//g' | sed 's/"//g')

# Get the branch name
frontend=$(git rev-parse --abbrev-ref HEAD)

# Directly set these
# Future enhancement: Set this in a single location
qpdf_version="10.6.3"
jbig2enc_version="0.29"

docker build . \
	--build-arg JBIG2ENC_VERSION="${jbig2enc_version}" \
	--build-arg QPDF_VERSION="${qpdf_version}" \
	--build-arg PIKEPDF_VERSION="${pikepdf_version}" \
	--build-arg PSYCOPG2_VERSION="${psycopg2_version}" \
	--build-arg FRONTEND_VERSION="${frontend}" "$@"
