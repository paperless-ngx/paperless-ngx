#!/bin/bash

set -e


VERSION=$1

if [ -z "$VERSION" ]
then
	echo "Need a version string."
	exit 1
fi

# source root directory of paperless
PAPERLESS_ROOT=$(git rev-parse --show-toplevel)

# output directory
PAPERLESS_DIST="$PAPERLESS_ROOT/dist"
PAPERLESS_DIST_APP="$PAPERLESS_DIST/paperless-ng"

cd "$PAPERLESS_DIST_APP"

docker push "jonaswinkler/paperless-ng:$VERSION"
