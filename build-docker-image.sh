#!/usr/bin/env bash

# Helper script for building the Docker image locally.
# Parses and provides the nessecary versions of other images to Docker
# before passing in the rest of script args

# First Argument: The Dockerfile to build
# Other Arguments: Additional arguments to docker build

# Example Usage:
#	./build-docker-image.sh Dockerfile -t paperless-ngx:my-awesome-feature
#	./build-docker-image.sh docker-builders/Dockerfile.qpdf -t paperless-ngx-build-qpdf:x.y.z

set -eux

# Parse what we can from Pipfile.lock
pikepdf_version=$(jq ".default.pikepdf.version" Pipfile.lock  | sed 's/=//g' | sed 's/"//g')
psycopg2_version=$(jq ".default.psycopg2.version" Pipfile.lock | sed 's/=//g' | sed 's/"//g')
# Read this from the other config file
qpdf_version=$(jq ".qpdf.version" .build-config.json | sed 's/"//g')
jbig2enc_version=$(jq ".jbig2enc.version" .build-config.json | sed 's/"//g')
# Get the branch name
frontend=$(git rev-parse --abbrev-ref HEAD)

if [ ! -f "$1" ]; then
	echo "$1 is not a file, please provide the Dockerfile"
	exit 1
fi

docker build --file "$1" \
	--build-arg JBIG2ENC_VERSION="${jbig2enc_version}" \
	--build-arg QPDF_VERSION="${qpdf_version}" \
	--build-arg PIKEPDF_VERSION="${pikepdf_version}" \
	--build-arg PSYCOPG2_VERSION="${psycopg2_version}" \
	--build-arg FRONTEND_VERSION="${frontend}" "${@:2}" .
