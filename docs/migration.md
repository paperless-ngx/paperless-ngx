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
