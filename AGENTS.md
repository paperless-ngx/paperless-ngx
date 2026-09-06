# Fork boundaries

- Develop on `dev_szaiser` from the selected stable upstream release. Keep the
  patch series small; do not merge upstream `dev` or rewrite release tags.
- Read `fork/README.md` before changes. Preserve upstream behavior when the
  optional integration is disabled. Domain rules stay outside this repository.
- Tests and manual review use only official upstream fixtures and synthetic
  mocks. No production documents, OCR, metadata, credentials, configuration
  exports, database copies or anonymized derivatives, locally or in CI.
- Do not contact production services during tests. Use the isolated lab network.
- Keep Python and shell logic in `.py` and `.sh` files; workflows compose them.
- Run relevant upstream tests, fork checks and native UI smoke tests. A build is
  not proof of functional integration. Do not deploy from this repository.
