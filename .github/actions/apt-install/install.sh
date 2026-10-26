#!/usr/bin/env bash
set -euo pipefail

# Run as root in the timed child process. Only downloads may be interrupted.
if [ "${1:-}" = download ]; then
	download_archive_dir=$2
	shift 2
	apt-get update -q
	apt-get install -q --yes --no-install-recommends --download-only \
		-o "Dir::Cache::archives=$download_archive_dir" "$@"
	exit 0
fi

SUDO=()
if [ "$(id -u)" -ne 0 ]; then
	SUDO=(sudo)
fi
read -r -a requested_packages <<< "$PACKAGES"
mkdir -p "$CACHE_DIR"
touch "$CACHE_DIR/.keep"

# Hosted runners use a mirror list; job containers can point directly at Azure.
# Handle both layouts, leaving other repositories and signature checks intact.
if [ -f /etc/apt/apt-mirrors.txt ]; then
	"${SUDO[@]}" sed -i '\|azure\.archive\.ubuntu\.com|d' /etc/apt/apt-mirrors.txt
fi
for source in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
	if [ -f "$source" ]; then
		"${SUDO[@]}" sed -i 's|azure\.archive\.ubuntu\.com|archive.ubuntu.com|g' "$source"
	fi
done

for attempt in $(seq 1 "$ATTEMPTS"); do
	echo "::group::apt download attempt ${attempt}/${ATTEMPTS}"
	if timeout --kill-after=10 "$ATTEMPT_TIMEOUT" "${SUDO[@]}" bash "$0" download "$CACHE_DIR" "${requested_packages[@]}"; then
		echo "::endgroup::"
		# Apt handles aliases (e.g. libmagic1 -> libmagic1t64) and dependencies.
		"${SUDO[@]}" apt-get install -q --yes --no-install-recommends --no-download \
			-o "Dir::Cache::archives=$CACHE_DIR" "${requested_packages[@]}"
		# Allow the unprivileged cache action to read archives downloaded as root.
		find "$CACHE_DIR" -maxdepth 1 -name '*.deb' -exec "${SUDO[@]}" chmod a+r {} +
		exit 0
	fi
	echo "::endgroup::"
	echo "::warning::apt download attempt ${attempt}/${ATTEMPTS} failed or exceeded ${ATTEMPT_TIMEOUT}s"
done

echo "::error::apt download failed after ${ATTEMPTS} attempts"
exit 1
