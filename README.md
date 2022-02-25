[![ci](https://github.com/paperless-ngx/paperless-ngx/workflows/ci/badge.svg)](https://github.com/paperless-ngx/paperless-ngx/actions)
[![Crowdin](https://badges.crowdin.net/paperless-ngx/localized.svg)](https://crowdin.com/project/paperless-ngx)
[![Documentation Status](https://readthedocs.org/projects/paperless-ngx/badge/?version=latest)](https://paperless-ngx.readthedocs.io/en/latest/?badge=latest)
[![Coverage Status](https://coveralls.io/repos/github/paperless-ngx/paperless-ngx/badge.svg?branch=master)](https://coveralls.io/github/paperless-ngx/paperless-ngx?branch=master)
[![Chat on Matrix](https://matrix.to/img/matrix-badge.svg)](https://matrix.to/#/#paperless:adnidor.de)

![Paperless logo](https://github.com/paperless-ngx/paperless-ngx/raw/main/resources/logo/web/png/Black%20logo%20-%20no%20background.png#gh-light-mode-only)
![Paperless logo](https://github.com/paperless-ngx/paperless-ngx/raw/main/resources/logo/web/png/White%20logo%20-%20no%20background.png#gh-dark-mode-only)

<!-- omit in toc -->
# Paperless-ngx

Paperless-ngx is a document management system that transforms your physical documents into a searchable online archive so you can keep, well, *less paper*.

Paperless-ngx forked from [paperless-ng](https://github.com/jonaswinkler/paperless-ng) to continue the great work and distribute responsibility among a team of people. That discussion can be found in issues
[#1599](https://github.com/jonaswinkler/paperless-ng/issues/1599)
and [#1632](https://github.com/jonaswinkler/paperless-ng/issues/1632).

- [Features](#features)
- [Getting started](#getting-started)
- [How it Works](#how-it-works)
- [Contributing](#contributing)
	- [Documentation](#documentation)
	- [Translation](#translation)
	- [Feature Requests](#feature-requests)
	- [Questions? Something not working?](#questions-something-not-working)
- [Get in Touch](#get-in-touch)
- [Affiliated Projects](#affiliated-projects)
- [Important Note](#important-note)

# Features

![Dashboard](https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/master/docs/_static/screenshots/documents-largecards.png)

* Organize and index your scanned documents with tags, correspondents, types, and more.
* Performs OCR on your documents, adds selectable text to image only documents and adds tags, correspondents and document types to your documents.
* Supports PDF documents, images, plain text files, and Office documents (Word, Excel, Powerpoint, and LibreOffice equivalents).
	* Office document support is optional and provided by Apache Tika (see [configuration](https://paperless-ngx.readthedocs.io/en/latest/configuration.html#tika-settings))
* Paperless stores your documents plain on disk. Filenames and folders are managed by paperless and their format can be configured freely.
* Single page application front end.
	* Includes a dashboard that shows basic statistics and has document upload.
	* Filtering by tags, correspondents, types, and more.
	* Customizable views can be saved and displayed on the dashboard.
* Full text search helps you find what you need.
	* Auto completion suggests relevant words from your documents.
	* Results are sorted by relevance to your search query.
	* Highlighting shows you which parts of the document matched the query.
	* Searching for similar documents ("More like this")
* Email processing: Paperless adds documents from your email accounts.
	* Configure multiple accounts and filters for each account.
	* When adding documents from mail, paperless can move these mail to a new folder, mark them as read, flag them as important or delete them.
* Machine learning powered document matching.
	* Paperless learns from your documents and will be able to automatically assign tags, correspondents and types to documents once you've stored a few documents in paperless.
* Optimized for multi core systems: Paperless-ng consumes multiple documents in parallel.
* The integrated sanity checker makes sure that your document archive is in good health.

# Getting started

The recommended way to deploy paperless is docker-compose. The files in the `/docker/compose` directory are configured to pull the image from GHCR.io.

Please read the [documentation](https://paperless-ngx.readthedocs.io/en/latest/setup.html#installation) on how to get started.

Alternatively, you can install the dependencies and setup apache and a database server yourself. The [documentation](https://paperless-ngx.readthedocs.io/en/latest/setup.html#installation) has a step by step guide on how to do it.

# How it Works

Paperless does not control your scanner, it only helps you deal with what your scanner produces.

1. Buy a document scanner that can write to a place on your network.  If you need some inspiration, have a look at the [scanner recommendations](https://paperless-ngx.readthedocs.io/en/latest/scanners.html) page. Set it up to "scan to FTP" or something similar. It should be able to push scanned images to a server without you having to do anything.  Of course if your scanner doesn't know how to automatically upload the file somewhere, you can always do that manually. Paperless doesn't care how the documents get into its local consumption directory.

	- Alternatively, you can use any of the mobile scanning apps out there. We have an app that allows you to share documents with paperless, if you're on Android. See the section on affiliated projects below.

2. Wait for paperless to process your files. OCR is expensive, and depending on the power of your machine, this might take a bit of time.
3. Use the web frontend to sift through the database and find what you want.
4. Download the PDF you need/want via the web interface and do whatever you like with it.  You can even print it and send it as if it's the original. In most cases, no one will care or notice.

If you want to see paperless-ngx in action, [more screenshots are available in the documentation](https://paperless-ngx.readthedocs.io/en/latest/screenshots.html).

# Contributing

If you feel like contributing to the project, please do! Bug fixes, enhancements, visual fixes etc. are always welcome. If you want to implement something big: Please start a discussion about that! The [documentation](https://paperless-ngx.readthedocs.io/en/latest/extending.html) has some basic information on how to get started.

## Documentation

The documentation for Paperless-ngx is available on [ReadTheDocs](https://paperless-ngx.readthedocs.io/).

## Translation

Paperless-ngx is available in many languages that are coordinated on Crowdin. If you want to help out by translating paperless-ngx into your language, please head over to https://crwd.in/paperless-ngx, and thank you! More details about adding new languages to the code can be found in [CONTRIBUTING.md](https://github.com/paperless-ngx/paperless-ngx/blob/master/CONTRIBUTING.md#adding-a-new-language). Some notes about translation:

- There are two resources:
  - `src-ui/messages.xlf` contains the translation strings for the front end. This is the most important.
  - `django.po` contains strings for the administration section of paperless, which is nice to have translated.
- Most of the front-end strings are used on buttons, menu items, etc., so ideally the translated string should not be much longer than the English original.
- Translation units may contain placeholders. These usually mean that there's a name of a tag or document or something in the string. You can click on the placeholders to copy them.
- Translation units may contain plural expressions such as `{PLURAL_VAR, plural, =1 {one result} =0 {no results} other {<placeholder> results}}`. Copy these verbatim and translate only the content in the inner `{}` brackets. Example: `{PLURAL_VAR, plural, =1 {Ein Ergebnis} =0 {Keine Ergebnisse} other {<placeholder> Ergebnisse}}`
- Changes to translations on Crowdin will get pushed into the repository automatically.

## Feature Requests

Feature requests can be submitted via [GitHub Discussions](https://github.com/paperless-ngx/paperless-ngx/discussions/categories/feature-requests), you can search for existing ideas, add your own and vote for the ones you care about! Note that some older feature requests can also be found under [issues](https://github.com/paperless-ngx/paperless-ngx/issues).

## Questions? Something not working?

For bugs please [open an issue](https://github.com/paperless-ngx/paperless-ngx/issues) or [start a discussion](https://github.com/paperless-ngx/paperless-ngx/discussions) if you have questions.

# Get in Touch

People interested in continuing the work on paperless-ngx are connecting here on github and in a [Matrix Room](https://matrix.to/#/#paperless:adnidor.de) for realtime communication.

# Affiliated Projects

Paperless has been around a while now, and people are starting to build stuff on top of it.  If you're one of those people, we can add your project to this list:

* [Paperless App](https://github.com/bauerj/paperless_app): An Android/iOS app for Paperless-ngx. Also works with the original Paperless and Paperless-ng.
* [Paperless Share](https://github.com/qcasey/paperless_share). Share any files from your Android application with paperless. Very simple, but works with all of the mobile scanning apps out there that allow you to share scanned documents.
* [Scan to Paperless](https://github.com/sbrunner/scan-to-paperless): Scan and prepare (crop, deskew, OCR, ...) your documents for Paperless.

These projects also exist, but their status and compatibility with paperless-ngx is unknown.

* [paperless-cli](https://github.com/stgarf/paperless-cli): A golang command line binary to interact with a Paperless instance.

This project also exists, but needs updates to be compatible with paperless-ngx.

* [Paperless Desktop](https://github.com/thomasbrueggemann/paperless-desktop): A desktop UI for your Paperless installation.  Runs on Mac, Linux, and Windows.
	Known issues on Mac: (Could not load reminders and documents)

# Important Note

Document scanners are typically used to scan sensitive documents.  Things like your social insurance number, tax records, invoices, etc.  Everything is stored in the clear without encryption. This means that Paperless should never be run on an untrusted host.  Instead, I recommend that if you do want to use it, run it locally on a server in your own home.
