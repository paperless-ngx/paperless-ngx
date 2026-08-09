#!/bin/sh
# Source s6 container environment for interactive shells.
# Ensures variables resolved from *_FILE secret injection are visible
# when using 'docker exec bash'. Does not affect s6 services (those
# use with-contenv directly). Has no effect in non-container contexts
# because the directory will not exist.
# Note: sh/dash shells opened via 'docker exec sh' are not covered;
# only bash-based sessions benefit from this file.
_pngx_contenv="/run/s6/container_environment"
if [ -d "${_pngx_contenv}" ]; then
	for _pngx_f in "${_pngx_contenv}"/*; do
		[ -f "${_pngx_f}" ] || continue
		_pngx_name=$(basename "${_pngx_f}")
		_pngx_val=$(cat "${_pngx_f}")
		export "${_pngx_name}=${_pngx_val}"
	done
fi
unset _pngx_contenv _pngx_f _pngx_name _pngx_val
