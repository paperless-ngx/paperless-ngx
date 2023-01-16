#!/usr/bin/env bash

# Helper script for building the Docker image locally.
# Parses and provides the nessecary versions of other images to Docker
# before passing in the rest of script args.

# First Argument: The Dockerfile to build
# Other Arguments: Additional arguments to docker build

# Example Usage:
#	./build-docker-image.sh Dockerfile -t paperless-ngx:my-awesome-feature

set -eu

if ! command -v jq &> /dev/null ;  then
	echo "jq required"
	exit 1
elif [ ! -f "$1" ]; then
	echo "$1 is not a file, please provide the Dockerfile"
	exit 1
fi

# Get the branch name (used for caching)
branch_name=$(git rev-parse --abbrev-ref HEAD)

# Parse eithe Pipfile.lock or the .build-config.json
jbig2enc_version=$(jq -r '.jbig2enc.version' .build-config.json)
qpdf_version=$(jq -r '.qpdf.version' .build-config.json)
psycopg2_version=$(jq -r '.default.psycopg2.version | gsub("=";"")' Pipfile.lock)
pikepdf_version=$(jq -r '.default.pikepdf.version | gsub("=";"")' Pipfile.lock)
pillow_version=$(jq -r '.default.pillow.version | gsub("=";"")' Pipfile.lock)
lxml_version=$(jq -r '.default.lxml.version | gsub("=";"")' Pipfile.lock)

base_filename="$(basename -- "${1}")"
build_args_str=""
cache_from_str=""

case "${base_filename}" in

	*.jbig2enc)
		build_args_str="--build-arg JBIG2ENC_VERSION=${jbig2enc_version}"
		cache_from_str="--cache-from ghcr.io/paperless-ngx/paperless-ngx/builder/cache/jbig2enc:${jbig2enc_version}"
		;;

	*.psycopg2)
		build_args_str="--build-arg PSYCOPG2_VERSION=${psycopg2_version}"
		cache_from_str="--cache-from ghcr.io/paperless-ngx/paperless-ngx/builder/cache/psycopg2:${psycopg2_version}"
		;;

	*.qpdf)
		build_args_str="--build-arg QPDF_VERSION=${qpdf_version}"
		cache_from_str="--cache-from ghcr.io/paperless-ngx/paperless-ngx/builder/cache/qpdf:${qpdf_version}"
		;;

	*.pikepdf)
		build_args_str="--build-arg QPDF_VERSION=${qpdf_version} --build-arg PIKEPDF_VERSION=${pikepdf_version} --build-arg PILLOW_VERSION=${pillow_version} --build-arg LXML_VERSION=${lxml_version}"
		cache_from_str="--cache-from ghcr.io/paperless-ngx/paperless-ngx/builder/cache/pikepdf:${pikepdf_version}"
		;;

	Dockerfile)
		build_args_str="--build-arg QPDF_VERSION=${qpdf_version} --build-arg PIKEPDF_VERSION=${pikepdf_version} --build-arg PSYCOPG2_VERSION=${psycopg2_version} --build-arg JBIG2ENC_VERSION=${jbig2enc_version}"
		cache_from_str="--cache-from ghcr.io/paperless-ngx/paperless-ngx/builder/cache/app:${branch_name} --cache-from ghcr.io/paperless-ngx/paperless-ngx/builder/cache/app:dev"
		;;

	*)
		echo "Unable to match ${base_filename}"
		exit 1
		;;
esac

read -r -a build_args_arr <<< "${build_args_str}"
read -r -a cache_from_arr <<< "${cache_from_str}"

set -eux

docker buildx build --file "${1}" \
	--progress=plain \
	--output=type=docker \
	"${cache_from_arr[@]}" \
	"${build_args_arr[@]}" \
	"${@:2}" .
