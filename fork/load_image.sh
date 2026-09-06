#!/usr/bin/env bash
set -euo pipefail

# Keep the Docker-built image for publishing; run acceptance with the same
# rootless Podman networking as local review, without granting lab egress.
docker save "$PAPERLESS_TEST_IMAGE" | podman load
docker_image_id=$(docker image inspect "$PAPERLESS_TEST_IMAGE" --format '{{.Id}}')
podman_image_id=$(podman image inspect "$PAPERLESS_TEST_IMAGE" --format '{{.Id}}')
[[ "${docker_image_id#sha256:}" == "${podman_image_id#sha256:}" ]]
echo "Acceptance runtime uses the exact built image: $docker_image_id"
