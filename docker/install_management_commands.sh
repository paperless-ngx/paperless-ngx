#!/usr/bin/env bash

# Run this script to generate the management commands again (for example if a new command is create or the template is updated)

set -eu

for command in document_archiver \
	document_exporter \
	document_importer \
	mail_fetcher \
	document_create_classifier \
	document_index \
	document_llmindex \
	document_renamer \
	document_retagger \
	document_thumbnails \
	document_sanity_checker \
	document_fuzzy_match \
	manage_superuser \
	convert_mariadb_uuid \
	prune_audit_logs \
	createsuperuser;
do
	echo "installing $command..."
	sed "s/management_command/$command/g" management_script.sh >"$PWD/rootfs/usr/local/bin/$command"
	chmod u=rwx,g=rwx,o=rx "$PWD/rootfs/usr/local/bin/$command"
done
