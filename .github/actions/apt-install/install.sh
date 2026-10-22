#!/usr/bin/env bash
set -euo pipefail

SUDO=()
if [ "$(id -u)" -ne 0 ]; then
	SUDO=(sudo)
fi

# Inputs are package names, separated by whitespace (not shell expressions).
read -r -a requested_packages <<< "$PACKAGES"
mkdir -p "$CACHE_DIR"

install_local() {
	local archives=("$CACHE_DIR"/*.deb)
	if [ -e "${archives[0]}" ]; then
		# Local .deb arguments pin the downloaded versions. No package lists or
		# network access are needed, and apt still runs all package maintainer scripts.
		"${SUDO[@]}" chmod a+r "${archives[@]}"
		"${SUDO[@]}" apt-get install -q --yes --no-install-recommends \
			--no-download -o "Dir::Cache::archives=$CACHE_DIR" "${archives[@]}"
	fi
	# An empty bundle is valid when the runner already includes every package.
	local package
	for package in "${requested_packages[@]}"; do
		[ "$(dpkg-query -W -f='${Status}' "$package")" = "install ok installed" ]
	done
}

if [ "$CACHE_HIT" = true ]; then
	echo "Installing cached apt packages without contacting package repositories"
	install_local
	exit 0
fi

# The hosted runner gives Azure priority 1. A slow transfer never triggers its
# fallback mirrors, so retrying alone keeps selecting the same unhealthy mirror.
if [ -f /etc/apt/apt-mirrors.txt ]; then
	"${SUDO[@]}" sed -i '\|azure\.archive\.ubuntu\.com|d' /etc/apt/apt-mirrors.txt
fi

# Download first so the bundle contains every missing transitive dependency.
# Keep downloads outside apt's default cache, which Docker cleanup hooks may wipe.
download_packages() {
	"${SUDO[@]}" apt-get update -q --error-on=any
	"${SUDO[@]}" apt-get install -q --yes --no-install-recommends \
		--download-only -o "Dir::Cache::archives=$CACHE_DIR" "${requested_packages[@]}"
}
# Recreate the sudo and package arrays in the timed child process.
if [ "${1:-}" = download ]; then
	download_packages
	exit 0
fi

for attempt in $(seq 1 "$ATTEMPTS"); do
	echo "::group::apt download attempt ${attempt}/${ATTEMPTS}"
	if timeout --kill-after=10 "$ATTEMPT_TIMEOUT" bash "$0" download; then
		echo "::endgroup::"
		install_local
		touch "$CACHE_DIR/complete"
		exit 0
	fi
	echo "::endgroup::"
	echo "::warning::apt download attempt ${attempt}/${ATTEMPTS} failed or exceeded ${ATTEMPT_TIMEOUT}s"
done

echo "::error::apt download failed after ${ATTEMPTS} attempts"
exit 1
