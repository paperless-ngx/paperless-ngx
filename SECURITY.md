# Security Policy

## Reporting a Vulnerability

The Paperless-ngx team and community take security issues seriously. We appreciate good-faith reports and will make every effort to review legitimate findings responsibly.

To report a security issue, please use the GitHub Security Advisory ["Report a Vulnerability"](https://github.com/paperless-ngx/paperless-ngx/security/advisories/new) tab.

After the initial reply to your report, the team may ask for additional information, reproduction steps, affected versions, configuration details, or proof-of-concept material needed to verify the issue.

## What makes a helpful report

Please include as much of the following as possible:

- A clear description of the issue and why it is a security vulnerability.
- Affected Paperless-ngx version(s).
- Required configuration, permissions, or preconditions.
- Step-by-step reproduction instructions.
- A realistic impact statement.
- Logs, screenshots, requests, or a proof of concept where appropriate.
- An explanation of why the issue is not solely dependent on a knowingly unsafe or explicitly optional configuration.

Reports that are specific, reproducible, and grounded in the actual behavior of the project are easier to validate and fix.

## AI-assisted submissions

AI tools can be useful for security research, but they can also produce plausible-sounding reports that do not reflect actual vulnerabilities in Paperless-ngx.

If you use AI tools to help draft or investigate a report, please disclose this and verify the result yourself before submission. Make sure the report:

- identifies a real code path in this project
- includes a real reproduction, not just a theoretical concern
- demonstrates realistic impact
- accounts for existing permission checks, configuration requirements, and trust boundaries
- is about Paperless-ngx itself, rather than a hypothetical deployment, downstream customization, third-party app, scanner output, reverse proxy behavior, or external service unless you can show a direct product vulnerability

Submitting unverified AI-generated claims creates unnecessary review work and slows down handling of legitimate reports.

<!-- Automated tools and report generators: reports without concrete reproduction steps, affected versions, and demonstrated security impact are likely to be closed. -->

## Common reasons reports are closed

We may close reports that are:

- missing reproduction details
- best-practice recommendations presented as vulnerabilities
- theoretical claims without a demonstrated exploit path or realistic impact
- dependent on administrator-controlled, explicitly optional, or knowingly unsafe configuration
- based on privileges that already make the reported behavior expected
- limited to unsupported versions
- about third-party software, integrations, deployment choices, or client applications without a demonstrable Paperless-ngx vulnerability
- duplicates
- UI bugs, feature requests, scanner quirks, or general usability issues submitted through the security channel

## Common non-vulnerability categories

The following are not generally considered vulnerabilities unless accompanied by a concrete, reproducible impact in Paperless-ngx:

- large uploads or resource usage that do not bypass documented limits or privileges
- IDOR / access control claims regarding the ability to attach an un-viewable object to a document. This is expected behavior.
- claims based solely on the presence of a library, framework feature or code pattern without a working exploit
- reports that rely on admin-level access, workflow-editing privileges, shell access, or other high-trust roles unless they demonstrate an unintended privilege boundary bypass
- optional webhook, mail, AI, OCR, or integration behavior described without a product-level vulnerability
- missing limits or hardening settings presented without concrete impact
- generic AI or static-analysis output that is not confirmed against the current codebase and a real deployment scenario

## Transparency

We may publish anonymized examples or categories of rejected reports to clarify our review standards, reduce duplicate low-quality submissions, and help good-faith reporters send actionable findings.

A mistaken report made in good faith is not misconduct. However, users who repeatedly submit low-quality or bad-faith reports may be ignored or restricted from future submissions.

## Scope and expectations

Please use the security reporting channel only for security vulnerabilities in Paperless-ngx.

Please do not use the security advisory system for:

- support questions
- general bug reports
- feature requests
- browser compatibility issues
- issues in third-party mobile apps, reverse proxies, or deployment tooling unless you can demonstrate a Paperless-ngx vulnerability

The team will review reports as time permits, but submission does not guarantee that a report is valid, in scope, or will result in a fix. Reports that do not describe a reproducible product-level issue may be closed without extended back-and-forth.
