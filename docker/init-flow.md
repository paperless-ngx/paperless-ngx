# Container init flow

Startup order of the s6-rc oneshot services under `docker/rootfs/etc/s6-overlay/s6-rc.d/`. An arrow `A --> B` means B lists A in its `dependencies.d/`, so B waits for A. Redundant (transitive) edges are omitted.

Each labelled box is a group of services that can run in parallel: every service in it starts as soon as its own dependencies finish, so services in the same box run in parallel. A service does not wait for the rest of its group, only for the arrows pointing at it. Long-running services such as `init-tesseract-langs` (package installs) overlap with several later steps.

```mermaid
flowchart TD
    subgraph w3 ["Run in parallel"]
        init-tesseract-langs
        init-modify-user
        init-wait-for-db
        init-wait-for-redis
    end
    subgraph w4 ["Run in parallel"]
        init-folders
        init-compile-bytecode
    end
    subgraph w6 ["Run in parallel"]
        init-search-index
        init-llmindex-migrate
        init-superuser
    end

    base --> init-start --> init-env-file

    init-env-file --> init-tesseract-langs
    init-env-file --> init-modify-user
    init-env-file --> init-wait-for-db
    init-env-file --> init-wait-for-redis
    init-start --> init-compile-bytecode

    init-modify-user --> init-folders
    init-modify-user --> init-compile-bytecode

    init-folders --> init-migrations
    init-compile-bytecode --> init-migrations
    init-wait-for-db --> init-migrations

    init-migrations --> init-search-index
    init-migrations --> init-llmindex-migrate
    init-migrations --> init-superuser

    init-tesseract-langs --> init-search-index
    init-tesseract-langs --> init-llmindex-migrate
    init-tesseract-langs --> init-system-checks
    init-superuser --> init-system-checks

    init-search-index --> init-custom-init
    init-system-checks --> init-custom-init
    init-wait-for-redis --> init-custom-init

    init-custom-init --> init-complete
    init-llmindex-migrate --> init-complete
```

`init-search-index` and `init-llmindex-migrate` run `manage.py`, which runs the Django system checks, including the check that the configured OCR languages are installed, so they wait for `init-tesseract-langs`.
