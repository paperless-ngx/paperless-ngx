#!/bin/bash

# Check for trailing whitespace at end of lines.

# Exit on first failing command.
set -e
# Exit on unset variable.
set -u

FOUND_TRAILING_WHITESPACE=0

while read -r line; do
  if grep \
    "\s$" \
    --line-number \
    --with-filename \
    --binary-files=without-match \
    --exclude="*.svg" \
    --exclude="*.eps" \
    "${line}"; then
    echo "ERROR: Found trailing whitespace" >&2;
    FOUND_TRAILING_WHITESPACE=1
  fi
done < <(git ls-files)

exit "${FOUND_TRAILING_WHITESPACE}"
