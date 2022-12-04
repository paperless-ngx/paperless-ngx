[![ci](https://github.com/paperless-ngx/paperless-ngx/workflows/ci/badge.svg)](https://github.com/paperless-ngx/paperless-ngx/actions)
[![Crowdin](https://badges.crowdin.net/paperless-ngx/localized.svg)](https://crowdin.com/project/paperless-ngx)
[![Documentation Status](https://img.shields.io/github/deployments/paperless-ngx/paperless-ngx/github-pages?label=docs)](https://docs.paperless-ngx.com)
[![Coverage Status](https://coveralls.io/repos/github/paperless-ngx/paperless-ngx/badge.svg?branch=master)](https://coveralls.io/github/paperless-ngx/paperless-ngx?branch=master)
[![Chat on Matrix](https://matrix.to/img/matrix-badge.svg)](https://matrix.to/#/%23paperlessngx%3Amatrix.org)
[![demo](https://cronitor.io/badges/ve7ItY/production/W5E_B9jkelG9ZbDiNHUPQEVH3MY.svg)](https://demo.paperless-ngx.com)

<p align="center">
<img src="https://github.com/paperless-ngx/paperless-ngx/raw/main/resources/logo/web/png/Black%20logo%20-%20no%20background.png#gh-light-mode-only" width="50%" />
<img src="https://github.com/paperless-ngx/paperless-ngx/raw/main/resources/logo/web/png/White%20logo%20-%20no%20background.png#gh-dark-mode-only" width="50%" />
</p>

<!-- omit in toc -->

# Paperless-ngx

Paperless-ngx is a document management system that transforms your physical documents into a searchable online archive so you can keep, well, _less paper_.

Paperless-ngx forked from [paperless-ng](https://github.com/jonaswinkler/paperless-ng) to continue the great work and distribute responsibility of supporting and advancing the project among a team of people. [Consider joining us!](#community-support) Discussion of this transition can be found in issues
[#1599](https://github.com/jonaswinkler/paperless-ng/issues/1599) and [#1632](https://github.com/jonaswinkler/paperless-ng/issues/1632).

A demo is available at [demo.paperless-ngx.com](https://demo.paperless-ngx.com) using login `demo` / `demo`. _Note: demo content is reset frequently and confidential information should not be uploaded._

- [Features](#features)
- [Getting started](#getting-started)
- [Contributing](#contributing)
  - [Community Support](#community-support)
  - [Translation](#translation)
  - [Feature Requests](#feature-requests)
  - [Bugs](#bugs)
- [Affiliated Projects](#affiliated-projects)
- [Important Note](#important-note)

# Features

![Dashboard](https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/main/docs/assets/screenshots/documents-smallcards.png#gh-light-mode-only)
![Dashboard](https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/main/docs/assets/screenshots/documents-smallcards-dark.png#gh-dark-mode-only)

- Organize and index your scanned documents with tags, correspondents, types, and more.
- Performs OCR on your documents, adds selectable text to image only documents and adds tags, correspondents and document types to your documents.
- Supports PDF documents, images, plain text files, and Office documents (Word, Excel, Powerpoint, and LibreOffice equivalents).
  - Office document support is optional and provided by Apache Tika (see [configuration](https://docs.paperless-ngx.com/configuration/#tika))
- Paperless stores your documents plain on disk. Filenames and folders are managed by paperless and their format can be configured freely.
- Single page application front end.
  - Includes a dashboard that shows basic statistics and has document upload.
  - Filtering by tags, correspondents, types, and more.
  - Customizable views can be saved and displayed on the dashboard.
- Full text search helps you find what you need.
  - Auto completion suggests relevant words from your documents.
  - Results are sorted by relevance to your search query.
  - Highlighting shows you which parts of the document matched the query.
  - Searching for similar documents ("More like this")
- Email processing: Paperless adds documents from your email accounts.
  - Configure multiple accounts and filters for each account.
  - When adding documents from mail, paperless can move these mail to a new folder, mark them as read, flag them as important or delete them.
- Machine learning powered document matching.
  - Paperless-ngx learns from your documents and will be able to automatically assign tags, correspondents and types to documents once you've stored a few documents in paperless.
- Optimized for multi core systems: Paperless-ngx consumes multiple documents in parallel.
- The integrated sanity checker makes sure that your document archive is in good health.
- [More screenshots are available in the documentation](https://docs.paperless-ngx.com/#screenshots).

# Getting started

The easiest way to deploy paperless is docker-compose. The files in the [`/docker/compose` directory](https://github.com/paperless-ngx/paperless-ngx/tree/main/docker/compose) are configured to pull the image from Github Packages.

If you'd like to jump right in, you can configure a docker-compose environment with our install script:

```bash
bash -c "$(curl -L https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/main/install-paperless-ngx.sh)"
```

Alternatively, you can install the dependencies and setup apache and a database server yourself. The [documentation](https://docs.paperless-ngx.com/setup/#installation) has a step by step guide on how to do it.

Migrating from Paperless-ng is easy, just drop in the new docker image! See the [documentation on migrating](https://docs.paperless-ngx.com/setup/#migrating-to-paperless-ngx) for more details.

<!-- omit in toc -->

### Documentation

The documentation for Paperless-ngx is available at [https://docs.paperless-ngx.com](https://docs.paperless-ngx.com/).

# Contributing

If you feel like contributing to the project, please do! Bug fixes, enhancements, visual fixes etc. are always welcome. If you want to implement something big: Please start a discussion about that! The [documentation](https://docs.paperless-ngx.com/development/) has some basic information on how to get started.

## Community Support

People interested in continuing the work on paperless-ngx are encouraged to reach out here on github and in the [Matrix Room](https://matrix.to/#/#paperless:adnidor.de). If you would like to contribute to the project on an ongoing basis there are multiple [teams](https://github.com/orgs/paperless-ngx/people) (frontend, ci/cd, etc) that could use your help so please reach out!

## Translation

Paperless-ngx is available in many languages that are coordinated on Crowdin. If you want to help out by translating paperless-ngx into your language, please head over to https://crwd.in/paperless-ngx, and thank you! More details can be found in [CONTRIBUTING.md](https://github.com/paperless-ngx/paperless-ngx/blob/main/CONTRIBUTING.md#translating-paperless-ngx).

## Feature Requests

Feature requests can be submitted via [GitHub Discussions](https://github.com/paperless-ngx/paperless-ngx/discussions/categories/feature-requests), you can search for existing ideas, add your own and vote for the ones you care about.

## Bugs

For bugs please [open an issue](https://github.com/paperless-ngx/paperless-ngx/issues) or [start a discussion](https://github.com/paperless-ngx/paperless-ngx/discussions) if you have questions.

# Affiliated Projects

Paperless has been around a while now, and people are starting to build stuff on top of it. If you're one of those people, we can add your project to this list:

- [Paperless App](https://github.com/bauerj/paperless_app): An Android/iOS app for Paperless-ngx. Also works with the original Paperless and Paperless-ng.
- [Paperless Share](https://github.com/qcasey/paperless_share). Share any files from your Android application with paperless. Very simple, but works with all of the mobile scanning apps out there that allow you to share scanned documents.
- [Scan to Paperless](https://github.com/sbrunner/scan-to-paperless): Scan and prepare (crop, deskew, OCR, ...) your documents for Paperless.
- [Paperless Mobile](https://github.com/astubenbord/paperless-mobile): A modern, feature rich mobile application for Paperless.

These projects also exist, but their status and compatibility with paperless-ngx is unknown.

- [paperless-cli](https://github.com/stgarf/paperless-cli): A golang command line binary to interact with a Paperless instance.

This project also exists, but needs updates to be compatible with paperless-ngx.

- [Paperless Desktop](https://github.com/thomasbrueggemann/paperless-desktop): A desktop UI for your Paperless installation. Runs on Mac, Linux, and Windows.
  Known issues on Mac: (Could not load reminders and documents)

# Important Note

Document scanners are typically used to scan sensitive documents. Things like your social insurance number, tax records, invoices, etc. Everything is stored in the clear without encryption. This means that Paperless should never be run on an untrusted host. Instead, I recommend that if you do want to use it, run it locally on a server in your own home.
