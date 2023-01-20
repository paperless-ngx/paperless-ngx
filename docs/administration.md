# Administration

## Making backups {#backup}

Multiple options exist for making backups of your paperless instance,
depending on how you installed paperless.

Before making backups, make sure that paperless is not running.

Options available to any installation of paperless:

- Use the [document exporter](#exporter). The document exporter exports all your documents,
  thumbnails and metadata to a specific folder. You may import your
  documents into a fresh instance of paperless again or store your
  documents in another DMS with this export.
- The document exporter is also able to update an already existing
  export. Therefore, incremental backups with `rsync` are entirely
  possible.

!!! caution

    You cannot import the export generated with one version of paperless in
    a different version of paperless. The export contains an exact image of
    the database, and migrations may change the database layout.

Options available to docker installations:

- Backup the docker volumes. These usually reside within
  `/var/lib/docker/volumes` on the host and you need to be root in
  order to access them.

  Paperless uses 4 volumes:

  - `paperless_media`: This is where your documents are stored.
  - `paperless_data`: This is where auxillary data is stored. This
    folder also contains the SQLite database, if you use it.
  - `paperless_pgdata`: Exists only if you use PostgreSQL and
    contains the database.
  - `paperless_dbdata`: Exists only if you use MariaDB and contains
    the database.

Options available to bare-metal and non-docker installations:

- Backup the entire paperless folder. This ensures that if your
  paperless instance crashes at some point or your disk fails, you can
  simply copy the folder back into place and it works.

  When using PostgreSQL or MariaDB, you'll also have to backup the
  database.

### Restoring {#migrating-restoring}

## Updating Paperless {#updating}

### Docker Route {#docker-updating}

If a new release of paperless-ngx is available, upgrading depends on how
you installed paperless-ngx in the first place. The releases are
available at the [release
page](https://github.com/paperless-ngx/paperless-ngx/releases).

First of all, ensure that paperless is stopped.

```shell-session
$ cd /path/to/paperless
$ docker-compose down
```

After that, [make a backup](#backup).

1. If you pull the image from the docker hub, all you need to do is:

   ```shell-session
   $ docker-compose pull
   $ docker-compose up
   ```

   The docker-compose files refer to the `latest` version, which is
   always the latest stable release.

2. If you built the image yourself, do the following:

   ```shell-session
   $ git pull
   $ docker-compose build
   $ docker-compose up
   ```

Running `docker-compose up` will also apply any new database migrations.
If you see everything working, press CTRL+C once to gracefully stop
paperless. Then you can start paperless-ngx with `-d` to have it run in
the background.

!!! note

    In version 0.9.14, the update process was changed. In 0.9.13 and
    earlier, the docker-compose files specified exact versions and pull
    won't automatically update to newer versions. In order to enable
    updates as described above, either get the new `docker-compose.yml`
    file from
    [here](https://github.com/paperless-ngx/paperless-ngx/tree/master/docker/compose)
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
    [bare metal installations](/setup#bare_metal).

2.  Update python requirements. Keep in mind to activate your virtual
    environment before that, if you use one.

    ```shell-session
    $ pip install -r requirements.txt
    ```

3.  Migrate the database.

    ```shell-session
    $ cd src
    $ python3 manage.py migrate
    ```

    This might not actually do anything. Not every new paperless version
    comes with new database migrations.

## Downgrading Paperless {#downgrade-paperless}

Downgrades are possible. However, some updates also contain database
migrations (these change the layout of the database and may move data).
In order to move back from a version that applied database migrations,
you'll have to revert the database migration _before_ downgrading, and
then downgrade paperless.

This table lists the compatible versions for each database migration
number.

| Migration number | Version range   |
| ---------------- | --------------- |
| 1011             | 1.0.0           |
| 1012             | 1.1.0 - 1.2.1   |
| 1014             | 1.3.0 - 1.3.1   |
| 1016             | 1.3.2 - current |

Execute the following management command to migrate your database:

```shell-session
$ python3 manage.py migrate documents <migration number>
```

!!! note

    Some migrations cannot be undone. The command will issue errors if that
    happens.

## Management utilities {#management-commands}

Paperless comes with some management commands that perform various
maintenance tasks on your paperless instance. You can invoke these
commands in the following way:

With docker-compose, while paperless is running:

```shell-session
$ cd /path/to/paperless
$ docker-compose exec webserver <command> <arguments>
```

With docker, while paperless is running:

```shell-session
$ docker exec -it <container-name> <command> <arguments>
```

Bare metal:

```shell-session
$ cd /path/to/paperless/src
$ python3 manage.py <command> <arguments>
```

All commands have built-in help, which can be accessed by executing them
with the argument `--help`.

### Document exporter {#exporter}

The document exporter exports all your data from paperless into a folder
for backup or migration to another DMS.

If you use the document exporter within a cronjob to backup your data
you might use the `-T` flag behind exec to suppress "The input device
is not a TTY" errors. For example:
`docker-compose exec -T webserver document_exporter ../export`

```
document_exporter target [-sm] [-c] [-f] [-p] [-d] [-na] [-nt]

optional arguments:
-sm, --split-manifest
-c, --compare-checksums
-f, --use-filename-format
-p, --use-filename-prefix
-d, --delete
-na, --no-archive
-nt, --no-thumbnail
-z  --zip
```

`target` is a folder to which the data gets written. This includes
documents, thumbnails and a `manifest.json` file. The manifest contains
all metadata from the database (correspondents, tags, etc).

If `-sm` or `--split-manifest` is provided, information about document
will be placed in individual json files.

When you use the provided docker compose script, specify `../export` as
the target. This path inside the container is automatically mounted on
your host on the folder `export`.

If the target directory already exists and contains files, paperless
will assume that the contents of the export directory are a previous
export and will attempt to update the previous export. Paperless will
only export changed and added files. Paperless determines whether a file
has changed by inspecting the file attributes "date/time modified" and
"size". If that does not work out for you, specify
`--compare-checksums` and paperless will attempt to compare file
checksums instead. This is slower.

Paperless will not remove any existing files in the export directory. If
you want paperless to also remove files that do not belong to the
current export such as files from deleted documents, specify `--delete`.
Be careful when pointing paperless to a directory that already contains
other files.

Paperless will not export archive files if you use `--no-archive`. After
importing, These files can be generated again by using `document_archiver`.
It can make sense to omit these files from backup as their content and checksum
can change (new archiver algorithm) and may then cause additional used space in
a deduplicated backup.

Paperless will not export thumbnails if you use `--no-thumbnail`. After
importing, These files can be generated again by using `document_thumbnails`.
It can make sense to omit these files from backup as their content and checksum
can change (new thumbnail generation algorithm) and may then cause additional
used space in a deduplicated backup.

If `-z` or `--zip` is provided, the export will be a zipfile
in the target directory, named according to the current date.

The filenames generated by this command follow the format
`[date created] [correspondent] [title].[extension]`. If you want
paperless to use `PAPERLESS_FILENAME_FORMAT` for exported filenames
instead, specify `--use-filename-format`.

If `-p` or `--use-filename-prefix` is provided, Files will be exported
in dedicated folders according to their nature: `archive`, `originals`,
`thumbnails` or `json`

!!! warning

    If exporting with the file name format, there may be errors due to
    your operating system's maximum path lengths.  Try adjusting the export
    target or consider not using the filename format.

### Document importer {#importer}

The document importer takes the export produced by the [Document
exporter](#exporter) and imports it into paperless.

The importer works just like the exporter. You point it at a directory,
and the script does the rest of the work:

```
document_importer source
```

When you use the provided docker compose script, put the export inside
the `export` folder in your paperless source directory. Specify
`../export` as the `source`.

!!! note

    Importing from a previous version of Paperless may work, but for best
    results it is suggested to match the versions.

### Document retagger {#retagger}

Say you've imported a few hundred documents and now want to introduce a
tag or set up a new correspondent, and apply its matching to all of the
currently-imported docs. This problem is common enough that there are
tools for it.

```
document_retagger [-h] [-c] [-T] [-t] [-i] [--use-first] [-f]

optional arguments:
-c, --correspondent
-T, --tags
-t, --document_type
-s, --storage_path
-i, --inbox-only
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
This network needs to be updated whenever somethings in your data
changes. The docker image takes care of that automatically with the task
scheduler. You can manually renew the classifier by invoking the
following management command:

```
document_create_classifier
```

This command takes no arguments.

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
[assign custom filenames to your documents](/advanced_usage#file-name-handling), you can use this command to move all your files after
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

- Missing original files.
- Missing archive files.
- Inaccessible original files due to improper permissions.
- Inaccessible archive files due to improper permissions.
- Corrupted original documents by comparing their checksum against
  what is stored in the database.
- Corrupted archive documents by comparing their checksum against what
  is stored in the database.
- Missing thumbnails.
- Inaccessible thumbnails due to improper permissions.
- Documents without any content (warning).
- Orphaned files in the media directory (warning). These are files
  that are not referenced by any document im paperless.

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

!!! note

    As of October 2022 Microsoft no longer supports IMAP authentication
    for Exchange servers, thus Exchange is no longer supported until a
    solution is implemented in the Python IMAP library used by Paperless.
    See [learn.microsoft.com](https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/deprecation-of-basic-authentication-exchange-online)

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

    Encryption is deprecated since [paperless-ng 0.9](/changelog#paperless-ng-090) and doesn't really
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
