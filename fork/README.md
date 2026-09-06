# Fork development and releases

This fork follows stable [Paperless-ngx releases](https://github.com/paperless-ngx/paperless-ngx/releases).
The development branch is `dev_szaiser`, initially based on `v3.1.3`.
The current increment supplies build and isolated-review tooling. Application
behavior is unchanged; the external suggestion-provider extension comes next.

## Test-data boundary

All tests, including local manual review, use upstream repository fixtures and
synthetic mocks only. Never use production documents, Content, metadata, database
dumps, credentials, configuration exports or anonymized derivatives. Never
connect tests to production Paperless, Finance, Prefect or inference services.
Public CI artifacts and images contain application source and synthetic test
results only.

## Local review

Requirements: rootless Podman with podman-compose 1.5.0; Python 3.
The stack has its own PostgreSQL database, Redis, document volumes and a
deterministic native-AI mock. Its network is internal and only the Paperless UI
is published, on loopback. No production configuration is loaded.

```sh
export PAPERLESS_TEST_IMAGE=ghcr.io/paperless-ngx/paperless-ngx:3.1.3
bash fork/lab.sh up
bash fork/lab.sh smoke
```

Use the upstream image only to establish the baseline. For fork acceptance, set
`PAPERLESS_TEST_IMAGE` to the exact published fork digest.

Local review and CI acceptance both use Podman. Docker's bridge implementation
can leave host ports unpublished on an internal-only network; see the
[upstream report](https://github.com/moby/moby/discussions/53256). The lab keeps
its internal-only network and loopback binding.

Open <http://localhost:18080>, sign in with `reviewer` /
`synthetic-review-only`, and open the uploaded **Upstream fixture**. Click
**Suggest** to load **Synthetic review example** and existing fixture taxonomy.
Requesting suggestions leaves saved metadata unchanged. Click a suggestion to
edit the form, then Save to persist it. These deliberately fixed responses test
integration and UI behavior, not classification quality.

The automated browser check uses Playwright 1.59.0:

```sh
uv run --no-project --with playwright==1.59.0 python -m playwright install chromium
uv run --no-project --with playwright==1.59.0 python fork/browser_smoke.py
```

On NixOS, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to the installed Chromium binary
instead of downloading a browser. The test selects a native title suggestion,
checks that it is unsaved, clicks Save and verifies persistence. It restores the
fixture title afterwards and checks the editor at mobile width.

```sh
bash fork/lab.sh status
bash fork/lab.sh logs
bash fork/lab.sh stop
```

`down` removes this project's containers and network, retaining test volumes.
The helper has no volume-deletion command. Do not upload personal files through
the test UI. The mock is a test double for the existing AI protocol, not the
future document-aware provider or a production proxy.

## Release contract

GitHub Actions first runs the reusable upstream backend and frontend tests,
then builds the upstream Dockerfile for `linux/amd64` with Docker Buildx. It
loads that same image into Podman, verifies its image ID, tests it in the
isolated stack, and publishes successful branch builds to
`ghcr.io/szaiser/paperless-ngx` with a `sha-<commit>` tag. Fork release tags use
`szaiser-v<upstream-version>-<revision>`, for example `szaiser-v3.1.3-1`.
Retain released tags and images unchanged. Deployments pin the resulting digest;
building or publishing never deploys to a server.

The repository owner enables Actions for the fork and makes the GHCR package
public. Publishing uses the job-scoped `GITHUB_TOKEN`; CI needs no infrastructure
credentials. Set `dev_szaiser` as the fork's default branch for manual workflow
dispatch. Upstream release tags retain their original meaning.

## Updating the upstream base

1. Fetch stable release tags from `upstream`; keep `origin` pointing at this fork.
2. Create a temporary update branch from `dev_szaiser` and rebase only the fork
   commits onto the selected stable release tag, never upstream `dev`.
3. Compare the old and new patch series with `git range-diff`; run upstream tests
   and isolated native-UI acceptance against the new image.
4. Coordinate with other contributors before updating `dev_szaiser` using
   `--force-with-lease`. Never move a published release tag.
5. Publish a new fork release. Review migrations and recovery requirements before
   separately updating the production image digest.

## Integration boundary

The next increment adds an optional external provider shared by native Suggest
and Apply AI Suggestions, explicit document context, cache/freshness handling,
and completion notification. Rules, inference and domain add-ons remain outside
Paperless. Add-ons write their owned custom fields through the Paperless API.
This extension is not implemented by the lab mock.
