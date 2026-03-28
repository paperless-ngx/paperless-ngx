# v3 Migration Guide

## Consumer Settings Changes

The v3 consumer command uses a [different library](https://watchfiles.helpmanual.io/) to unify
the watching for new files in the consume directory. For the user, this removes several configuration options related to delays and retries
and replaces with a single unified setting. It also adjusts how the consumer ignore filtering happens, replaced `fnmatch` with `regex` and
separating the directory ignore from the file ignore.

### Summary

| Old Setting                    | New Setting                                                                         | Notes                                                                                |
| ------------------------------ | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `CONSUMER_POLLING`             | [`CONSUMER_POLLING_INTERVAL`](configuration.md#PAPERLESS_CONSUMER_POLLING_INTERVAL) | Renamed for clarity                                                                  |
| `CONSUMER_INOTIFY_DELAY`       | [`CONSUMER_STABILITY_DELAY`](configuration.md#PAPERLESS_CONSUMER_STABILITY_DELAY)   | Unified for all modes                                                                |
| `CONSUMER_POLLING_DELAY`       | _Removed_                                                                           | Use `CONSUMER_STABILITY_DELAY`                                                       |
| `CONSUMER_POLLING_RETRY_COUNT` | _Removed_                                                                           | Automatic with stability tracking                                                    |
| `CONSUMER_IGNORE_PATTERNS`     | [`CONSUMER_IGNORE_PATTERNS`](configuration.md#PAPERLESS_CONSUMER_IGNORE_PATTERNS)   | **Now regex, not fnmatch**; user patterns are added to (not replacing) default ones  |
| _New_                          | [`CONSUMER_IGNORE_DIRS`](configuration.md#PAPERLESS_CONSUMER_IGNORE_DIRS)           | Additional directories to ignore; user entries are added to (not replacing) defaults |

## Encryption Support

Document and thumbnail encryption is no longer supported. This was previously deprecated in [paperless-ng 0.9.3](https://github.com/paperless-ngx/paperless-ngx/blob/dev/docs/changelog.md#paperless-ng-093)

Users must decrypt their document using the `decrypt_documents` command before upgrading.

## Barcode Scanner Changes

Support for [pyzbar](https://github.com/NaturalHistoryMuseum/pyzbar) has been removed. The underlying libzbar library has
seen no updates in 16 years and is largely unmaintained, and the pyzbar Python wrapper last saw a release in March 2022. In
practice, pyzbar struggled with barcode detection reliability, particularly on skewed, low-contrast, or partially
obscured barcodes. [zxing-cpp](https://github.com/zxing-cpp/zxing-cpp) is actively maintained, significantly more
reliable at finding barcodes, and now ships pre-built wheels for both x86_64 and arm64, removing the need to build the library.

The `CONSUMER_BARCODE_SCANNER` setting has been removed. zxing-cpp is now the only backend.

### Summary

| Old Setting                | New Setting | Notes                             |
| -------------------------- | ----------- | --------------------------------- |
| `CONSUMER_BARCODE_SCANNER` | _Removed_   | zxing-cpp is now the only backend |

### Action Required

- If you were already using `CONSUMER_BARCODE_SCANNER=ZXING`, simply remove the setting.
- If you had `CONSUMER_BARCODE_SCANNER=PYZBAR` or were using the default, no functional changes are needed beyond
  removing the setting. zxing-cpp supports all the same barcode formats and you should see improved detection
  reliability.
- The `libzbar0` / `libzbar-dev` system packages are no longer required and can be removed from any custom Docker
  images or host installations.

## Database Engine

`PAPERLESS_DBENGINE` is now required to use PostgreSQL or MariaDB. Previously, the
engine was inferred from the presence of `PAPERLESS_DBHOST`, with `PAPERLESS_DBENGINE`
only needed to select MariaDB over PostgreSQL.

SQLite users require no changes, though they may explicitly set their engine if desired.

#### Action Required

PostgreSQL and MariaDB users must add `PAPERLESS_DBENGINE` to their environment:

```yaml
# v2 (PostgreSQL inferred from PAPERLESS_DBHOST)
PAPERLESS_DBHOST: postgres

# v3 (engine must be explicit)
PAPERLESS_DBENGINE: postgresql
PAPERLESS_DBHOST: postgres
```

See [`PAPERLESS_DBENGINE`](configuration.md#PAPERLESS_DBENGINE) for accepted values.

## Database Advanced Options

The individual SSL, timeout, and pooling variables have been removed in favor of a
single [`PAPERLESS_DB_OPTIONS`](configuration.md#PAPERLESS_DB_OPTIONS) string. This
consolidates a growing set of engine-specific variables into one place, and allows
any option supported by the underlying database driver to be set without requiring a
dedicated environment variable for each.

The removed variables and their replacements are:

| Removed Variable          | Replacement in `PAPERLESS_DB_OPTIONS`                                        |
| ------------------------- | ---------------------------------------------------------------------------- |
| `PAPERLESS_DBSSLMODE`     | `sslmode=<value>` (PostgreSQL) or `ssl_mode=<value>` (MariaDB)               |
| `PAPERLESS_DBSSLROOTCERT` | `sslrootcert=<path>` (PostgreSQL) or `ssl.ca=<path>` (MariaDB)               |
| `PAPERLESS_DBSSLCERT`     | `sslcert=<path>` (PostgreSQL) or `ssl.cert=<path>` (MariaDB)                 |
| `PAPERLESS_DBSSLKEY`      | `sslkey=<path>` (PostgreSQL) or `ssl.key=<path>` (MariaDB)                   |
| `PAPERLESS_DB_POOLSIZE`   | `pool.max_size=<value>` (PostgreSQL only)                                    |
| `PAPERLESS_DB_TIMEOUT`    | `timeout=<value>` (SQLite) or `connect_timeout=<value>` (PostgreSQL/MariaDB) |

The deprecated variables will continue to function for now but will be removed in a
future release. A deprecation warning is logged at startup for each deprecated variable
that is still set.

#### Action Required

Users with any of the deprecated variables set should migrate to `PAPERLESS_DB_OPTIONS`.
Multiple options are combined in a single value:

```bash
PAPERLESS_DB_OPTIONS="sslmode=require;sslrootcert=/certs/ca.pem;pool.max_size=10"
```

## OCR and Archive File Generation Settings

The settings that control OCR behaviour and archive file generation have been redesigned. The old settings that coupled these two concerns together are **removed** — old values are not silently honoured; a startup warning is logged if any removed variable is still set in your environment.

### Removed settings

| Removed Setting                             | Replacement                                                           |
| ------------------------------------------- | --------------------------------------------------------------------- |
| `PAPERLESS_OCR_MODE=skip`                   | `PAPERLESS_OCR_MODE=auto` (new default)                               |
| `PAPERLESS_OCR_MODE=skip_noarchive`         | `PAPERLESS_OCR_MODE=auto` + `PAPERLESS_ARCHIVE_FILE_GENERATION=never` |
| `PAPERLESS_OCR_SKIP_ARCHIVE_FILE=never`     | `PAPERLESS_ARCHIVE_FILE_GENERATION=always`                            |
| `PAPERLESS_OCR_SKIP_ARCHIVE_FILE=with_text` | `PAPERLESS_ARCHIVE_FILE_GENERATION=auto` (new default)                |
| `PAPERLESS_OCR_SKIP_ARCHIVE_FILE=always`    | `PAPERLESS_ARCHIVE_FILE_GENERATION=never`                             |

### What changed and why

Previously, `OCR_MODE` conflated two independent concerns: whether to run OCR and whether to produce an archive. `skip` meant "skip OCR if text exists, but always produce an archive". `skip_noarchive` meant "skip OCR if text exists, and also skip the archive". This made it impossible to, for example, disable OCR entirely while still producing archives.

The new settings are independent:

- [`PAPERLESS_OCR_MODE`](configuration.md#PAPERLESS_OCR_MODE) controls OCR: `auto` (default), `force`, `redo`, `off`.
- [`PAPERLESS_ARCHIVE_FILE_GENERATION`](configuration.md#PAPERLESS_ARCHIVE_FILE_GENERATION) controls archive production: `auto` (default), `always`, `never`.

### Action Required

Remove any `PAPERLESS_OCR_SKIP_ARCHIVE_FILE` variable from your environment. If you relied on `OCR_MODE=skip` or `OCR_MODE=skip_noarchive`, update accordingly:

```bash
# v2: skip OCR when text present, always archive
PAPERLESS_OCR_MODE=skip
# v3: equivalent (auto is the new default)
# No change needed — auto is the default

# v2: skip OCR when text present, skip archive too
PAPERLESS_OCR_MODE=skip_noarchive
# v3: equivalent
PAPERLESS_OCR_MODE=auto
PAPERLESS_ARCHIVE_FILE_GENERATION=never

# v2: always skip archive
PAPERLESS_OCR_SKIP_ARCHIVE_FILE=always
# v3: equivalent
PAPERLESS_ARCHIVE_FILE_GENERATION=never

# v2: skip archive only for born-digital docs
PAPERLESS_OCR_SKIP_ARCHIVE_FILE=with_text
# v3: equivalent (auto is the new default)
PAPERLESS_ARCHIVE_FILE_GENERATION=auto
```

### Remote OCR parser

If you use the **remote OCR parser** (Azure AI), note that it always produces a
searchable PDF and stores it as the archive copy. `ARCHIVE_FILE_GENERATION=never`
has no effect for documents handled by the remote parser — the archive is produced
unconditionally by the remote engine.

## OpenID Connect Token Endpoint Authentication

Some existing OpenID Connect setups may require an explicit token endpoint authentication method after upgrading to v3.

#### Action Required

If OIDC login fails at the callback with an `invalid_client` error, add `token_auth_method` to the provider `settings` in
[`PAPERLESS_SOCIALACCOUNT_PROVIDERS`](configuration.md#PAPERLESS_SOCIALACCOUNT_PROVIDERS).

For example:

```json
{
  "openid_connect": {
    "APPS": [
      {
        ...
        "settings": {
          "server_url": "https://login.example.com",
          "token_auth_method": "client_secret_basic"
        }
      }
    ]
  }
}
```
