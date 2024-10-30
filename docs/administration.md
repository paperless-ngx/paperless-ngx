# Administration

## Making backups {#backup}

Multiple options exist for making backups of your paperless instance,
depending on how you installed paperless.

Before making a backup, it's probably best to make sure that paperless is not actively
consuming documents at that time.

Options available to any installation of paperless:

-   Use the [document exporter](#exporter). The document exporter exports all your documents,
    thumbnails, metadata, and database contents to a specific folder. You may import your
    documents and settings into a fresh instance of paperless again or store your
    documents in another DMS with this export.

    The document exporter is also able to update an already existing
    export. Therefore, incremental backups with `rsync` are entirely
    possible.

    The exporter does not include API tokens and they will need to be re-generated after importing.

!!! caution

    You cannot import the export generated with one version of paperless in
    a different version of paperless. The export contains an exact image of
    the database, and migrations may change the database layout.

Options available to docker installations:

-   Backup the docker volumes. These usually reside within
    `/var/lib/docker/volumes` on the host and you need to be root in
    order to access them.

    Paperless uses 4 volumes:

    -   `paperless_media`: This is where your documents are stored.
    -   `paperless_data`: This is where auxiliary data is stored. This
        folder also contains the SQLite database, if you use it.
    -   `paperless_pgdata`: Exists only if you use PostgreSQL and
        contains the database.
    -   `paperless_dbdata`: Exists only if you use MariaDB and contains
        the database.

Options available to bare-metal and non-docker installations:

-   Backup the entire paperless folder. This ensures that if your
    paperless instance crashes at some point or your disk fails, you can
    simply copy the folder back into place and it works.

    When using PostgreSQL or MariaDB, you'll also have to backup the
    database.

### Restoring {#migrating-restoring}

If you've backed-up Paperless-ngx using the [document exporter](#exporter),
restoring can simply be done with the [document importer](#importer).

Of course, other backup strategies require restoring any volumes, folders and database
copies you created in the steps above.

## Updating Paperless {#updating}

### Docker Route {#docker-updating}

If a new release of paperless-ngx is available, upgrading depends on how
you installed paperless-ngx in the first place. The releases are
available at the [release
page](https://github.com/paperless-ngx/paperless-ngx/releases).

First of all, make sure no active processes (like consumption) are running, then [make a backup](#backup).

After that, ensure that paperless is stopped:

```shell-session
$ cd /path/to/paperless
$ docker compose down
```

1.  If you pull the image from the docker hub, all you need to do is:

    ```shell-session
    $ docker compose pull
    $ docker compose up
    ```

    The Docker Compose files refer to the `latest` version, which is
    always the latest stable release.

1.  If you built the image yourself, do the following:

    ```shell-session
    $ git pull
    $ docker compose build
    $ docker compose up
    ```

Running `docker compose up` will also apply any new database migrations.
If you see everything working, press CTRL+C once to gracefully stop
paperless. Then you can start paperless-ngx with `-d` to have it run in
the background.

!!! note

    In version 0.9.14, the update process was changed. In 0.9.13 and
    earlier, the Docker Compose files specified exact versions and pull
    won't automatically update to newer versions. In order to enable
    updates as described above, either get the new `docker-compose.yml`
    file from
    [here](https://github.com/paperless-ngx/paperless-ngx/tree/main/docker/compose)
    or edit the `docker-compose.yml` file, find the line that says

    ```
    image: ghcr.io/paperless-ngx/paperless-ngx:0.9.x
    ```

    and replace the version with `latest`:

    ```
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    ```

!!! note

    In version 1.7.1 and onwards, the Docker image can now be pinned to a
    release series. This is often combined with automatic updaters such as
    Watchtower to allow safer unattended upgrading to new bugfix releases
    only. It is still recommended to always review release notes before
    upgrading. To pin your install to a release series, edit the
    `docker-compose.yml` find the line that says

    ```
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    ```

    and replace the version with the series you want to track, for
    example:

    ```
    image: ghcr.io/paperless-ngx/paperless-ngx:1.7
    ```

### Bare Metal Route {#bare-metal-updating}

After grabbing the new release and unpacking the contents, do the
following:

1.  Update dependencies. New paperless version may require additional
    dependencies. The dependencies required are listed in the section
    about
    [bare metal installations](setup.md#bare_metal).

2.  Update python requirements. Keep in mind to activate your virtual
    environment before that, if you use one.

    ```shell-session
    $ pip install -r requirements.txt
    ```

    !!! note

        At times, some dependencies will be removed from requirements.txt.
        Comparing the versions and removing no longer needed dependencies
        will keep your system or virtual environment clean and prevent
        possible conflicts.

3.  Migrate the database.

    ```shell-session
    $ cd src
    $ python3 manage.py migrate # (1)
    ```

    1.  Including `sudo -Hu <paperless_user>` may be required

    This might not actually do anything. Not every new paperless version
    comes with new database migrations.

### Database Upgrades

In general, paperless does not require a specific version of PostgreSQL or MariaDB and it is
safe to update them to newer versions. However, you should always take a backup and follow
the instructions from your database's documentation for how to upgrade between major versions.

For PostgreSQL, refer to [Upgrading a PostgreSQL Cluster](https://www.postgresql.org/docs/current/upgrading.html).

For MariaDB, refer to [Upgrading MariaDB](https://mariadb.com/kb/en/upgrading/)

You may also use the exporter and importer with the `--data-only` flag, after creating a new database with the updated version of PostgreSQL or MariaDB.

!!! warning

    You should not change any settings, especially paths, when doing this or there is a
    risk of data loss

## Management utilities {#management-commands}

Paperless comes with some management commands that perform various
maintenance tasks on your paperless instance. You can invoke these
commands in the following way:

With Docker Compose, while paperless is running:

```shell-session
$ cd /path/to/paperless
$ docker compose exec webserver <command> <arguments>
```

With docker, while paperless is running:

```shell-session
$ docker exec -it <container-name> <command> <arguments>
```

Bare metal:

```shell-session
$ cd /path/to/paperless/src
$ python3 manage.py <command> <arguments> # (1)
```

1.  Including `sudo -Hu <paperless_user>` may be required

All commands have built-in help, which can be accessed by executing them
with the argument `--help`.

### Document exporter {#exporter}

The document exporter exports all your data (including your settings
and database contents) from paperless into a folder for backup or
migration to another DMS.

If you use the document exporter within a cronjob to backup your data
you might use the `-T` flag behind exec to suppress "The input device
is not a TTY" errors. For example:
`docker compose exec -T webserver document_exporter ../export`

```
document_exporter target [-c] [-d] [-f] [-na] [-nt] [-p] [-sm] [-z]

optional arguments:
-c,  --compare-checksums
-cj, --compare-json
-d,  --delete
-f,  --use-filename-format
-na, --no-archive
-nt, --no-thumbnail
-p,  --use-folder-prefix
-sm, --split-manifest
-z,  --zip
-zn, --zip-name
--data-only
--no-progress-bar
--passphrase
```

`target` is a folder to which the data gets written. This includes
documents, thumbnails and a `manifest.json` file. The manifest contains
all metadata from the database (correspondents, tags, etc).

When you use the provided docker compose script, specify `../export` as
the target. This path inside the container is automatically mounted on
your host on the folder `export`.

If the target directory already exists and contains files, paperless
will assume that the contents of the export directory are a previous
export and will attempt to update the previous export. Paperless will
only export changed and added files. Paperless determines whether a file
has changed by inspecting the file attributes "date/time modified" and
"size". If that does not work out for you, specify `-c` or
`--compare-checksums` and paperless will attempt to compare file
checksums instead. This is slower. The manifest and metadata json files
are always updated, unless `cj` or `--compare-json` is specified.

Paperless will not remove any existing files in the export directory. If
you want paperless to also remove files that do not belong to the
current export such as files from deleted documents, specify `-d` or `--delete`.
Be careful when pointing paperless to a directory that already contains
other files.

The filenames generated by this command follow the format
`[date created] [correspondent] [title].[extension]`. If you want
paperless to use [`PAPERLESS_FILENAME_FORMAT`](configuration.md#PAPERLESS_FILENAME_FORMAT) for exported filenames
instead, specify `-f` or `--use-filename-format`.

If `-na` or `--no-archive` is provided, no archive files will be exported,
only the original files.

If `-nt` or `--no-thumbnail` is provided, thumbnail files will not be exported.

!!! note

    When using the `-na`/`--no-archive` or `-nt`/`--no-thumbnail` options
    the exporter will not output these files for backup.  After importing,
    the [sanity checker](#sanity-checker) will warn about missing thumbnails and archive files
    until they are regenerated with `document_thumbnails` or [`document_archiver`](#archiver).
    It can make sense to omit these files from backup as their content and checksum
    can change (new archiver algorithm) and may then cause additional used space in
    a deduplicated backup.

If `-p` or `--use-folder-prefix` is provided, files will be exported
in dedicated folders according to their nature: `archive`, `originals`,
`thumbnails` or `json`

If `-sm` or `--split-manifest` is provided, information about document
will be placed in individual json files, instead of a single JSON file. The main
manifest.json will still contain application wide information (e.g. tags, correspondent,
documenttype, etc)

If `-z` or `--zip` is provided, the export will be a zip file
in the target directory, named according to the current local date or the
value set in `-zn` or `--zip-name`.

If `--data-only` is provided, only the database will be exported. This option is intended
to facilitate database upgrades without needing to clean documents and thumbnails from the media directory.

If `--no-progress-bar` is provided, the progress bar will be hidden, rendering the
exporter quiet. This option is useful for scripting scenarios, such as when using the
exporter with `crontab`.

If `--passphrase` is provided, it will be used to encrypt certain fields in the export. This value
must be provided to import. If this value is lost, the export cannot be imported.

!!! warning

    If exporting with the file name format, there may be errors due to
    your operating system's maximum path lengths.  Try adjusting the export
    target or consider not using the filename format.

### Document importer {#importer}

The document importer takes the export produced by the [Document
exporter](#exporter) and imports it into paperless.

The importer works just like the exporter. You point it at a directory,
and the script does the rest of the work:

```shell
document_importer source
```

| Option              | Required | Default | Description                                                               |
| ------------------- | -------- | ------- | ------------------------------------------------------------------------- |
| source              | Yes      | N/A     | The directory containing an export                                        |
| `--no-progress-bar` | No       | False   | If provided, the progress bar will be hidden                              |
| `--data-only`       | No       | False   | If provided, only import data, do not import document files or thumbnails |
| `--passphrase`      | No       | N/A     | If your export was encrypted with a passphrase, must be provided          |

When you use the provided docker compose script, put the export inside
the `export` folder in your paperless source directory. Specify
`../export` as the `source`.

Note that .zip files (as can be generated from the exporter) are not supported. You must unzip them into
the target directory first.

!!! note

    Importing from a previous version of Paperless may work, but for best
    results it is suggested to match the versions.

!!! warning

    The importer should be run against a completely empty installation (database and directories) of Paperless-ngx.
    If using a data only import, only the database must be empty.

### Document retagger {#retagger}

Say you've imported a few hundred documents and now want to introduce a
tag or set up a new correspondent, and apply its matching to all of the
currently-imported docs. This problem is common enough that there are
tools for it.

```
document_retagger [-h] [-c] [-T] [-t] [-i] [--id-range] [--use-first] [-f]

optional arguments:
-c, --correspondent
-T, --tags
-t, --document_type
-s, --storage_path
-i, --inbox-only
--id-range
--use-first
-f, --overwrite
```

Run this after changing or adding matching rules. It'll loop over all
of the documents in your database and attempt to match documents
according to the new rules.

Specify any combination of `-c`, `-T`, `-t` and `-s` to have the
retagger perform matching of the specified metadata type. If you don't
specify any of these options, the document retagger won't do anything.

Specify `-i` to have the document retagger work on documents tagged with
inbox tags only. This is useful when you don't want to mess with your
already processed documents.

Specify `--id-range 1 100` to have the document retagger work only on a
specific range of document id´s. This can be useful if you have a lot of
documents and want to test the matching rules only on a subset of
documents.

When multiple document types or correspondents match a single document,
the retagger won't assign these to the document. Specify `--use-first`
to override this behavior and just use the first correspondent or type
it finds. This option does not apply to tags, since any amount of tags
can be applied to a document.

Finally, `-f` specifies that you wish to overwrite already assigned
correspondents, types and/or tags. The default behavior is to not assign
correspondents and types to documents that have this data already
assigned. `-f` works differently for tags: By default, only additional
tags get added to documents, no tags will be removed. With `-f`, tags
that don't match a document anymore get removed as well.

### Managing the Automatic matching algorithm

The _Auto_ matching algorithm requires a trained neural network to work.
This network needs to be updated whenever something in your data
changes. The docker image takes care of that automatically with the task
scheduler. You can manually renew the classifier by invoking the
following management command:

```
document_create_classifier
```

This command takes no arguments.

### Document thumbnails {#thumbnails}

Use this command to re-create document thumbnails. Optionally include the ` --document {id}` option to generate thumbnails for a specific document only.

You may also specify `--processes` to control the number of processes used to generate new thumbnails. The default is to utilize
a quarter of the available processors.

```
document_thumbnails
```

### Managing the document search index {#index}

The document search index is responsible for delivering search results
for the website. The document index is automatically updated whenever
documents get added to, changed, or removed from paperless. However, if
the search yields non-existing documents or won't find anything, you
may need to recreate the index manually.

```
document_index {reindex,optimize}
```

Specify `reindex` to have the index created from scratch. This may take
some time.

Specify `optimize` to optimize the index. This updates certain aspects
of the index and usually makes queries faster and also ensures that the
autocompletion works properly. This command is regularly invoked by the
task scheduler.

### Managing filenames {#renamer}

If you use paperless' feature to
[assign custom filenames to your documents](advanced_usage.md#file-name-handling), you can use this command to move all your files after
changing the naming scheme.

!!! warning

    Since this command moves your documents, it is advised to do a backup
    beforehand. The renaming logic is robust and will never overwrite or
    delete a file, but you can't ever be careful enough.

```
document_renamer
```

The command takes no arguments and processes all your documents at once.

Learn how to use
[Management Utilities](#management-commands).

### Sanity checker {#sanity-checker}

Paperless has a built-in sanity checker that inspects your document
collection for issues.

The issues detected by the sanity checker are as follows:

-   Missing original files.
-   Missing archive files.
-   Inaccessible original files due to improper permissions.
-   Inaccessible archive files due to improper permissions.
-   Corrupted original documents by comparing their checksum against
    what is stored in the database.
-   Corrupted archive documents by comparing their checksum against what
    is stored in the database.
-   Missing thumbnails.
-   Inaccessible thumbnails due to improper permissions.
-   Documents without any content (warning).
-   Orphaned files in the media directory (warning). These are files
    that are not referenced by any document in paperless.

```
document_sanity_checker
```

The command takes no arguments. Depending on the size of your document
archive, this may take some time.

### Fetching e-mail

Paperless automatically fetches your e-mail every 10 minutes by default.
If you want to invoke the email consumer manually, call the following
management command:

```
mail_fetcher
```

The command takes no arguments and processes all your mail accounts and
rules.

!!! tip

    To use OAuth access tokens for mail fetching,
    select the box to indicate the password is actually
    a token when creating or editing a mail account. The
    details for creating a token depend on your email
    provider.

### Creating archived documents {#archiver}

Paperless stores archived PDF/A documents alongside your original
documents. These archived documents will also contain selectable text
for image-only originals. These documents are derived from the
originals, which are always stored unmodified. If coming from an earlier
version of paperless, your documents won't have archived versions.

This command creates PDF/A documents for your documents.

```
document_archiver --overwrite --document <id>
```

This command will only attempt to create archived documents when no
archived document exists yet, unless `--overwrite` is specified. If
`--document <id>` is specified, the archiver will only process that
document.

!!! note

    This command essentially performs OCR on all your documents again,
    according to your settings. If you run this with
    `PAPERLESS_OCR_MODE=redo`, it will potentially run for a very long time.
    You can cancel the command at any time, since this command will skip
    already archived versions the next time it is run.

!!! note

    Some documents will cause errors and cannot be converted into PDF/A
    documents, such as encrypted PDF documents. The archiver will skip over
    these documents each time it sees them.

### Managing encryption {#encryption}

Documents can be stored in Paperless using GnuPG encryption.

!!! warning

    Encryption is deprecated since [paperless-ng 0.9](changelog.md#paperless-ng-090) and doesn't really
    provide any additional security, since you have to store the passphrase
    in a configuration file on the same system as the encrypted documents
    for paperless to work. Furthermore, the entire text content of the
    documents is stored plain in the database, even if your documents are
    encrypted. Filenames are not encrypted as well.

    Also, the web server provides transparent access to your encrypted
    documents.

    Consider running paperless on an encrypted filesystem instead, which
    will then at least provide security against physical hardware theft.

#### Enabling encryption

Enabling encryption is no longer supported.

#### Disabling encryption

Basic usage to disable encryption of your document store:

(Note: If `PAPERLESS_PASSPHRASE` isn't set already, you need to specify
it here)

```
decrypt_documents [--passphrase SECR3TP4SSPHRA$E]
```

### Detecting duplicates {#fuzzy_duplicate}

Paperless already catches and prevents upload of exactly matching documents,
however a new scan of an existing document may not produce an exact bit for bit
duplicate. But the content should be exact or close, allowing detection.

This tool does a fuzzy match over document content, looking for
those which look close according to a given ratio.

At this time, other metadata (such as correspondent or type) is not
taken into account by the detection.

```
document_fuzzy_match [--ratio] [--processes N]
```

| Option      | Required | Default             | Description                                                                                                                    |
| ----------- | -------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| --ratio     | No       | 85.0                | a number between 0 and 100, setting how similar a document must be for it to be reported. Higher numbers mean more similarity. |
| --processes | No       | 1/4 of system cores | Number of processes to use for matching. Setting 1 disables multiple processes                                                 |
| --delete    | No       | False               | If provided, one document of a matched pair above the ratio will be deleted.                                                   |

!!! warning

    If providing the `--delete` option, it is highly recommended to have a backup.
    While every effort has been taken to ensure proper operation, there is always the
    chance of deletion of a file you want to keep.
