#!/usr/bin/env bash
set -euo pipefail

[[ "$FORK_COMMIT" =~ ^[0-9a-f]{40}$ ]] || exit 2
image=ghcr.io/szaiser/paperless-ngx
tag="sha-${FORK_COMMIT}"
if [[ "$FORK_REF_TYPE" == tag ]]; then
	[[ "$FORK_REF_NAME" =~ ^szaiser-v[0-9]+\.[0-9]+\.[0-9]+-[0-9]+$ ]] || exit 2
	tag="$FORK_REF_NAME"
fi
# The exact image that passed the smoke test is published, never rebuilt here.
if docker manifest inspect "$image:$tag" >/dev/null 2>&1; then
	echo "Image tag already exists; retaining immutable $image:$tag"
	exit 0
fi
docker tag "$PAPERLESS_TEST_IMAGE" "$image:$tag"
docker push "$image:$tag"
docker inspect "$image:$tag" --format '{{json .RepoDigests}}'
