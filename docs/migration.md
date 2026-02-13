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

-   If you were already using `CONSUMER_BARCODE_SCANNER=ZXING`, simply remove the setting.
-   If you had `CONSUMER_BARCODE_SCANNER=PYZBAR` or were using the default, no functional changes are needed beyond
    removing the setting. zxing-cpp supports all the same barcode formats and you should see improved detection
    reliability.
-   The `libzbar0` / `libzbar-dev` system packages are no longer required and can be removed from any custom Docker
    images or host installations.
