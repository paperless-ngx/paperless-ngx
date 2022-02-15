#!/bin/bash

# Verify that all text files end in a trailing newline.

# Exit on first failing command.
set -e

# Exit on unset variable.
set -u

success=0

function is_plaintext_file() {
  local file="$1"
  if [[ $file == *.svg ]]; then
    echo ""
    return
  fi
  file --brief "${file}" | grep text
}

# Split strings on newlines.
IFS='
'
for file in $(git ls-files)
do
  if [[ -z $(is_plaintext_file "${file}") ]]; then
    continue
  fi

  if ! [[ -z "$(tail -c 1 "${file}")" ]]; then
    printf "File must end in a trailing newline: %s\n" "${file}" >&2
    success=255
  fi
done

exit "${success}"
