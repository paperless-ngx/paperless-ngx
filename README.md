[![ci](https://github.com/jonaswinkler/paperless-ng/workflows/ci/badge.svg)](https://github.com/jonaswinkler/paperless-ng/actions)
![Ansible Role](https://github.com/jonaswinkler/paperless-ng/workflows/Ansible%20Role/badge.svg)
[![Crowdin](https://badges.crowdin.net/paperless-ng/localized.svg)](https://crowdin.com/project/paperless-ng)
[![Documentation Status](https://readthedocs.org/projects/paperless-ng/badge/?version=latest)](https://paperless-ng.readthedocs.io/en/latest/?badge=latest)
[![Gitter](https://badges.gitter.im/paperless-ng/community.svg)](https://gitter.im/paperless-ng/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
[![Docker Hub Pulls](https://img.shields.io/docker/pulls/jonaswinkler/paperless-ng.svg)](https://hub.docker.com/r/jonaswinkler/paperless-ng)
[![Coverage Status](https://coveralls.io/repos/github/jonaswinkler/paperless-ng/badge.svg?branch=master)](https://coveralls.io/github/jonaswinkler/paperless-ng?branch=master)

# Paperless-ng

[Paperless (click me)](https://github.com/the-paperless-project/paperless) is an application by Daniel Quinn and contributors that indexes your scanned documents and allows you to easily search for documents and store metadata alongside your documents.

Paperless-ng is a fork of the original project, adding a new interface and many other changes under the hood. These key points should help you decide whether Paperless-ng is something you would prefer over Paperless:

* Interface: The new front end is the main interface for Paperless-ng, the old interface still exists but most customizations (such as thumbnails for the document list) have been removed.0
* Encryption: Paperless-ng does not support GnuPG anymore, since storing your data on encrypted file systems (that you optionally mount on demand) achieves about the same result.
* Resource usage: Paperless-ng does use a bit more resources than Paperless. Running the web server requires about 300MB of RAM or more, depending on the configuration. While adding documents, it requires about 300MB additional RAM, depending on the document. It still runs on Raspberry Pi (many users do that), but it has been generally geared to better use the resources of more powerful systems.
* API changes: If you rely on the REST API of paperless, some of its functionality has been changed.

For a detailed list of changes, have a look at the [change log](https://paperless-ng.readthedocs.io/en/latest/changelog.html) in the documentation, especially the section about the [0.9.0 release](https://paperless-ng.readthedocs.io/en/latest/changelog.html#paperless-ng-0-9-0).

# How it Works

Paperless does not control your scanner, it only helps you deal with what your scanner produces.

1. Buy a document scanner that can write to a place on your network.  If you need some inspiration, have a look at the [scanner recommendations](https://paperless-ng.readthedocs.io/en/latest/scanners.html) page. Set it up to "scan to FTP" or something similar. It should be able to push scanned images to a server without you having to do anything.  Of course if your scanner doesn't know how to automatically upload the file somewhere, you can always do that manually. Paperless doesn't care how the documents get into its local consumption directory.

	- Alternatively, you can use any of the mobile scanning apps out there. We have an app that allows you to share documents with paperless, if you're on Android. See the section on affiliated projects below.

2. Wait for paperless to process your files. OCR is expensive, and depending on the power of your machine, this might take a bit of time.
3. Use the web frontend to sift through the database and find what you want.
4. Download the PDF you need/want via the web interface and do whatever you like with it.  You can even print it and send it as if it's the original. In most cases, no one will care or notice.

Here's what you get:

![Dashboard](https://github.com/jonaswinkler/paperless-ng/raw/master/docs/_static/screenshots/dashboard.png)

If you want to see paperless-ng in action, [more screenshots are available in the documentation](https://paperless-ng.readthedocs.io/en/latest/screenshots.html).

# Features

* Performs OCR on your documents, adds selectable text to image only documents and adds tags, correspondents and document types to your documents.
* Supports PDF documents, images, plain text files, and Office documents (Word, Excel, Powerpoint, and LibreOffice equivalents).
	* Office document support is optional and provided by Apache Tika (see [configuration](https://paperless-ng.readthedocs.io/en/latest/configuration.html#tika-settings))
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

The recommended way to deploy paperless is docker-compose. The files in the /docker/compose directory are configured to pull the image from Docker Hub.

Read the [documentation](https://paperless-ng.readthedocs.io/en/latest/setup.html#installation) on how to get started.

Alternatively, you can install the dependencies and setup apache and a database server yourself. The documenation has a step by step guide on how to do it. Consider giving the Ansible role a shot, this essentially automates the entire bare metal installation process.

# Migrating from Paperless to Paperless-ng

Read the section about [migration](https://paperless-ng.readthedocs.io/en/latest/setup.html#migration-to-paperless-ng) in the documentation. Its also entirely possible to go back to Paperless by reverting the database migrations.

# Documentation

The documentation for Paperless-ng is available on [ReadTheDocs](https://paperless-ng.readthedocs.io/).

# Translation

Paperless is available in many different languages. Translation is coordinated at crowdin. If you want to help out by translating paperless into your language, please head over to https://github.com/jonaswinkler/paperless-ng/issues/212 for details!

# Feature Requests

Feature requests can be submitted via [GitHub Discussions](https://github.com/jonaswinkler/paperless-ng/discussions/categories/feature-requests), you can search for existing ideas, add your own and vote for the ones you care about! Note that some older feature requests can also be found under [issues](https://github.com/jonaswinkler/paperless-ng/issues).

# Questions? Something not working?

For bugs please [open an issue](https://github.com/jonaswinkler/paperless-ng/issues) or [start a discussion](https://github.com/jonaswinkler/paperless-ng/discussions) if you have questions.

## Feel like helping out?

There's still lots of things to be done, just have a look at open issues & discussions. If you feel like contributing to the project, please do! Bug fixes and improvements to the front end (I just can't seem to get some of these CSS things right) are always welcome. The documentation has some basic information on how to get started.

If you want to implement something big: Please start a discussion about that! Maybe I've already had something similar in mind and we can make it happen together. However, keep in mind that the general roadmap is to make the existing features stable and get them tested.

# Affiliated Projects

Paperless has been around a while now, and people are starting to build stuff on top of it.  If you're one of those people, we can add your project to this list:

* [Paperless App](https://github.com/bauerj/paperless_app): An Android/iOS app for Paperless. Updated to work with paperless-ng.
* [Paperless Share](https://github.com/qcasey/paperless_share). Share any files from your Android application with paperless. Very simple, but works with all of the mobile scanning apps out there that allow you to share scanned documents.
* [Scan to Paperless](https://github.com/sbrunner/scan-to-paperless): Scan and prepare (crop, deskew, OCR, ...) your documents for Paperless.

These projects also exist, but their status and compatibility with paperless-ng is unknown.

* [paperless-cli](https://github.com/stgarf/paperless-cli): A golang command line binary to interact with a Paperless instance.

This project also exists, but needs updates to be compatile with paperless-ng.

* [Paperless Desktop](https://github.com/thomasbrueggemann/paperless-desktop): A desktop UI for your Paperless installation.  Runs on Mac, Linux, and Windows.
	Known issues on Mac: (Could not load reminders and documents)

# Important Note

Document scanners are typically used to scan sensitive documents.  Things like your social insurance number, tax records, invoices, etc.  Everything is stored in the clear without encryption. This means that Paperless should never be run on an untrusted host.  Instead, I recommend that if you do want to use it, run it locally on a server in your own home.
