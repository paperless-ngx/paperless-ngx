#!/usr/bin/env bash

set -eu

for command in document_archiver document_exporter document_importer mail_fetcher document_create_classifier document_index document_renamer document_retagger document_thumbnails document_sanity_checker manage_superuser;
do
	echo "installing $command..."
	sed "s/management_command/$command/g" management_script.sh > /usr/local/bin/$command
	chmod +x /usr/local/bin/$command
done
