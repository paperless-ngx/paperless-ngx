#!/usr/bin/env bash

# Scans the environment variables for those with the suffix _FILE
# When located, checks the file exists, and exports the contents
# of the file as the same name, minus the suffix
# This allows the use of Docker secrets or mounted files
# to fill in any of the settings configurable via environment
# variables

set -eu

for line in $(printenv)
do
	# Extract the name of the environment variable
	env_name=${line%%=*}
	# Check if it ends in "_FILE"
	if [[ ${env_name} == *_FILE ]]; then
		# Extract the value of the environment
		env_value=${line#*=}

		# Check the file exists
		if [[ -f ${env_value} ]]; then

			# Trim off the _FILE suffix
			non_file_env_name=${env_name%"_FILE"}
			echo "Setting ${non_file_env_name} from file"

			# Reads the value from th file
			val="$(< "${!env_name}")"

			# Sets the normal name to the read file contents
			export "${non_file_env_name}"="${val}"

		else
			echo "File ${env_value} doesn't exist"
			exit 1
		fi
	fi
done
