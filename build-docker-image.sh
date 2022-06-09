#!/usr/bin/env bash

# Helper script for building the Docker image locally.
# Parses and provides the nessecary versions of other images to Docker
# before passing in the rest of script args.

# First Argument: The Dockerfile to build
# Other Arguments: Additional arguments to docker build

# Example Usage:
#	./build-docker-image.sh Dockerfile -t paperless-ngx:my-awesome-feature

set -eux

if ! command -v jq;  then
	echo "jq required"
	exit 1
elif [ ! -f "$1" ]; then
	echo "$1 is not a file, please provide the Dockerfile"
	exit 1
fi

# Parse what we can from Pipfile.lock
pikepdf_version=$(jq ".default.pikepdf.version" Pipfile.lock  | sed 's/=//g' | sed 's/"//g')
psycopg2_version=$(jq ".default.psycopg2.version" Pipfile.lock | sed 's/=//g' | sed 's/"//g')
# Read this from the other config file
qpdf_version=$(jq ".qpdf.version" .build-config.json | sed 's/"//g')
jbig2enc_version=$(jq ".jbig2enc.version" .build-config.json | sed 's/"//g')
# Get the branch name (used for caching)
branch_name=$(git rev-parse --abbrev-ref HEAD)

# https://docs.docker.com/develop/develop-images/build_enhancements/
# Required to use cache-from
export DOCKER_BUILDKIT=1

docker build --file "$1" \
	--progress=plain \
	--cache-from ghcr.io/paperless-ngx/paperless-ngx/builder/cache/app:"${branch_name}" \
	--cache-from ghcr.io/paperless-ngx/paperless-ngx/builder/cache/app:dev \
	--build-arg JBIG2ENC_VERSION="${jbig2enc_version}" \
	--build-arg QPDF_VERSION="${qpdf_version}" \
	--build-arg PIKEPDF_VERSION="${pikepdf_version}" \
	--build-arg PSYCOPG2_VERSION="${psycopg2_version}" "${@:2}" .
