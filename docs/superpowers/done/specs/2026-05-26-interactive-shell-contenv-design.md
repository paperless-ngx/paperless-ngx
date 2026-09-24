# Interactive Shell Container Environment

**Date:** 2026-05-26
**Branch:** fix-tanvity-index-lock (to be implemented on a new branch)
**Status:** Approved

## Problem

When paperless-ngx users open an interactive shell in the running container via `docker exec -it <container> bash`, they do not see environment variables resolved from `*_FILE` secret injection.

The `init-env-file` s6 init script reads `PAPERLESS_*_FILE` variables (e.g. `PAPERLESS_SECRET_KEY_FILE=/run/secrets/key`), reads the referenced file, and writes the resolved value (e.g. `PAPERLESS_SECRET_KEY=abc123`) to `/run/s6/container_environment/`. All s6-managed services and management command wrappers use the `#!/command/with-contenv` shebang, which reads that directory and injects all vars into the process environment before execution.

`docker exec bash` bypasses s6 entirely. It is a non-login interactive shell launched directly by the Docker daemon, which provides only the original Docker-configured environment (the `*_FILE` paths, not the resolved values). Any manual command a user runs — such as `document_exporter` or `manage.py` calls — will be missing the resolved secrets unless they happen to also be set as plain Docker env vars.

## Approach

Source `/run/s6/container_environment/` in every interactive bash shell opened in the container, mirroring what `with-contenv` does for s6 services.

Two hooks are needed because Debian uses different rc files for different shell types:

- **Non-login interactive** (`docker exec bash`): sources `/etc/bash.bashrc`
- **Login interactive** (`docker exec bash --login`): sources `/etc/profile`, which auto-sources all `/etc/profile.d/*.sh`

## Changes

### 1. `docker/rootfs/etc/profile.d/contenv.sh` (new file)

A POSIX-compatible shell script that exports all files in `/run/s6/container_environment/` as environment variables. Placed here so login shells pick it up automatically.

```sh
#!/bin/sh
# Source s6 container environment for interactive shells.
# Ensures variables resolved from *_FILE secret injection are visible
# when using 'docker exec bash'. Does not affect s6 services (those
# use with-contenv directly). Has no effect in non-container contexts
# because the directory will not exist.
# Note: sh/dash shells opened via 'docker exec sh' are not covered;
# only bash-based sessions benefit from this file.
_pngx_contenv="/run/s6/container_environment"
if [ -d "${_pngx_contenv}" ]; then
    for _pngx_f in "${_pngx_contenv}"/*; do
        [ -f "${_pngx_f}" ] || continue
        _pngx_name=$(basename "${_pngx_f}")
        _pngx_val=$(cat "${_pngx_f}")
        export "${_pngx_name}=${_pngx_val}"
    done
fi
unset _pngx_contenv _pngx_f _pngx_name _pngx_val
```

### 2. Dockerfile `main-app` stage (one line added)

Appends a source line to `/etc/bash.bashrc` so non-login interactive shells also pick up contenv. Added after the runtime package installation block, before the Python dependency installation.

```dockerfile
RUN echo '. /etc/profile.d/contenv.sh' >> /etc/bash.bashrc
```

`/etc/bash.bashrc` is provided by the Debian base image and installed during the apt step, so it exists by the time this `RUN` executes.

## Coverage

| How user gets a shell                    | Gets contenv?         | Mechanism                                |
| ---------------------------------------- | --------------------- | ---------------------------------------- |
| `docker exec -it container bash`         | Yes                   | `/etc/bash.bashrc` sources `contenv.sh`  |
| `docker exec -it container bash --login` | Yes                   | `/etc/profile.d/contenv.sh` auto-sourced |
| `docker exec -it container sh`           | No (known limitation) | `sh` sources neither file                |
| Management command wrappers              | Already worked        | `with-contenv` shebang                   |
| s6 services                              | Already worked        | `with-contenv` shebang                   |

## Edge Cases

**Shell opened before `init-env-file` completes:** The directory exists but may not yet contain all resolved vars. The script exports what is present; missing vars are simply absent. No error is produced.

**Variable value contains special characters:** `$(cat file)` strips only trailing newlines (which `init-env-file` already warns about). Other special characters are preserved correctly by the `export "NAME=VALUE"` form.

**Directory does not exist (non-container use):** The `[ -d ]` guard makes the script a no-op. Safe to include in any Debian-based image.

## Testing

No automated test is added. This is container-bootstrap shell plumbing with no Python code path. Manual verification: run the container with a `*_FILE` secret, `docker exec bash`, and confirm the resolved variable is present in the environment.
