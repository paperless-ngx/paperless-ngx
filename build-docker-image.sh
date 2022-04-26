#!/usr/bin/env bash

# Helper script for building the Docker image locally.
# Parses and provides the nessecary versions of other images to Docker
# before passing in the rest of script args.  A future enhancement
# would be to combine this with the CI script

# First Argument: The Dockerfile to build
# Other Arguments: Additional arguments to docker build

# Example Usage:
#	./build-docker-image.sh Dockerfile -t paperless-ngx:my-awesome-feature
#	./build-docker-image.sh docker-builders/Dockerfile.qpdf -t paperless-ngx-build-qpdf:x.y.z

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
# Get the branch name
frontend_version=$(git rev-parse --abbrev-ref HEAD)

# Get Git tags for building
# psycopg2 uses X_Y_Z git tags
psycopg2_git_tag=${psycopg2_version//./_}
# pikepdf uses vX.Y.Z
pikepdf_git_tag="v${pikepdf_version}"

docker build --file "$1" \
	--build-arg JBIG2ENC_VERSION="${jbig2enc_version}" \
	--build-arg QPDF_VERSION="${qpdf_version}" \
	--build-arg PIKEPDF_VERSION="${pikepdf_version}" \
	--build-arg PIKEPDF_GIT_TAG="${pikepdf_git_tag}" \
	--build-arg PSYCOPG2_VERSION="${psycopg2_version}" \
	--build-arg PSYCOPG2_GIT_TAG="${psycopg2_git_tag}" \
	--build-arg FRONTEND_VERSION="${frontend_version}" "${@:2}" .
