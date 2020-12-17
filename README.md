[![Build Status](https://travis-ci.org/jonaswinkler/paperless-ng.svg?branch=master)](https://travis-ci.org/jonaswinkler/paperless-ng)
[![Documentation Status](https://readthedocs.org/projects/paperless-ng/badge/?version=latest)](https://paperless-ng.readthedocs.io/en/latest/?badge=latest)
[![Docker Hub Pulls](https://img.shields.io/docker/pulls/jonaswinkler/paperless-ng.svg)](https://hub.docker.com/r/jonaswinkler/paperless-ng)
[![Coverage Status](https://coveralls.io/repos/github/jonaswinkler/paperless-ng/badge.svg?branch=master)](https://coveralls.io/github/jonaswinkler/paperless-ng?branch=master)

# Paperless-ng

[Paperless](https://github.com/the-paperless-project/paperless) is an application by Daniel Quinn and others that indexes your scanned documents and allows you to easily search for documents and store metadata alongside your documents.

Paperless-ng is a fork of the original project, adding a new interface and many other changes under the hood. For a detailed list of changes, have a look at the changelog in the documentation.

This project is still in development and some things may not work as expected.

# How it Works

Paperless does not control your scanner, it only helps you deal with what your scanner produces.

1. Buy a document scanner that can write to a place on your network.  If you need some inspiration, have a look at the [scanner recommendations](https://paperless-ng.readthedocs.io/en/latest/scanners.html) page. Set it up to "scan to FTP" or something similar. It should be able to push scanned images to a server without you having to do anything.  Of course if your scanner doesn't know how to automatically upload the file somewhere, you can always do that manually. Paperless doesn't care how the documents get into its local consumption directory.

	- Alternatively, you can use any of the mobile scanning apps out there. We have an app that allows you to share documents with paperless, if you're on Android. See the section on affiliated projects.

2. Wait for paperless to process your files. OCR is expensive, and depending on the power of your machine, this might take a bit of time.
3. Use the web frontend to sift through the database and find what you want.
4. Download the PDF you need/want via the web interface and do whatever you like with it.  You can even print it and send it as if it's the original. In most cases, no one will care or notice.

Here's what you get:

![Dashboard](https://github.com/jonaswinkler/paperless-ng/raw/master/docs/_static/screenshots/dashboard.png)

# Features

* Performs OCR on your documents, adds selectable text to image only documents and adds tags, correspondents and document types to your documents.
* Paperless stores your documents plain on disk. Filenames and folders are managed by paperless and can be configured freely.
* Single page application front end. Should be pretty snappy. Will be mobile friendly in the future.
	* Includes a dashboard that shows basic statistics and has document upload.
	* Filtering by tags, correspondents, types, and more.
	* Customizable views can be saved and displayed on the dashboard.
	* Full text search with auto completion, scored results and query highlighting allows you to quickly find what you need.
* Email processing: Paperless adds documents from your email accounts.
	* Configure multiple accounts and filters for each account.
	* When adding documents from mails, paperless can move these mails to a new folder, mark them as read, flag them or delete them.
* Machine learning powered document matching.
	* Paperless learns from your documents and will be able to automatically assign tags, correspondents and types to documents once you've stored a few documents in paperless.
* A task processor that processes documents in parallel and also tells you when something goes wrong. On modern multi core systems, consumption is blazing fast.
* Code cleanup in many, MANY areas. Some of the code from OG paperless was just overly complicated.
* More tests, more stability.

If you want to see some screenshots of paperless-ng in action, [some are available in the documentation](https://paperless-ng.readthedocs.io/en/latest/screenshots.html).

For a complete list of changes from paperless, check out the [changelog](https://paperless-ng.readthedocs.io/en/latest/changelog.html)

# Roadmap for 1.0

- Make the front end nice (except mobile).
- Test coverage at 90%.
- Fix whatever bugs I and you find.

## Roadmap for versions beyond 1.0

These are things that I want to add to paperless eventually. They are sorted by priority.

- **Bulk editing**. Add/remove metadata from multiple documents at once.
- **More search.** The search backend is incredibly versatile and customizable. Searching is the most important feature of this project and thus, I want to implement things like:
  - Group and limit search results by correspondent, show “more from this” links in the results.
  - Ability to search for “Similar documents” in the search results
- **Nested tags**. Organize tags in a hierarchical structure. This will combine the benefits of folders and tags in one coherent system.
- **An interactive consumer** that shows its progress for documents it processes on the web page.
	- With live updates ans websockets. This already works on a dev branch, but requires a lot of new dependencies, which I'm not particular happy about.
	- Notifications when a document was added with buttons to open the new document right away.
- **Arbitrary tag colors**. Allow the selection of any color with a color picker.

## On the chopping block.

- **GnuPG encrypion.** [Here's a note about encryption in paperless](https://paperless-ng.readthedocs.io/en/latest/administration.html#managing-encryption). The gist of it is that I don't see which attacks this implementation protects against. It gives a false sense of security to users who don't care about how it works.

# Getting started

The recommended way to deploy paperless is docker-compose. Don't clone the repository, grab the latest release to get started instead. The dockerfiles archive contains just the docker files which will pull the image from docker hub. The source archive contains everything you need to build the docker image yourself (i.e. if you want to run on Raspberry Pi).

Read the [documentation](https://paperless-ng.readthedocs.io/en/latest/setup.html#installation) on how to get started.

Alternatively, you can install the dependencies and setup apache and a database server yourself. The documenation has a step by step guide on how to do it.

# Migrating to paperless-ng

Read the section about [migration](https://paperless-ng.readthedocs.io/en/latest/setup.html#migration-to-paperless-ng) in the documentation. Its also entirely possible to go back to paperless by reverting the database migrations.

# Documentation

The documentation for Paperless-ng is available on [ReadTheDocs](https://paperless-ng.readthedocs.io/).

# Suggestions? Questions? Something not working?

Please open an issue and start a discussion about it!

## Feel like helping out?

There's still lots of things to be done, just have a look at that issue log. If you feel like contributing to the project, please do! Bug fixes and improvements to the front end (I just can't seem to get some of these CSS things right) are always welcome. The documentation has some basic information on how to get started.

If you want to implement something big: Please start a discussion about that in the issues! Maybe I've already had something similar in mind and we can make it happen together. However, keep in mind that the general roadmap is to make the existing features stable and get them tested. See the roadmap above.

# Affiliated Projects

Paperless has been around a while now, and people are starting to build stuff on top of it.  If you're one of those people, we can add your project to this list:

* [Paperless App](https://github.com/bauerj/paperless_app): An Android/iOS app for Paperless. Updated to work with paperless-ng.
* [Paperless Share](https://github.com/qcasey/paperless_share). Share any files from your Android application with paperless. Very simple, but works with all of the mobile scanning apps out there that allow you to share scanned documents.

These projects also exist, but their status and compatibility with paperless-ng is unknown.

* [Paperless Desktop](https://github.com/thomasbrueggemann/paperless-desktop): A desktop UI for your Paperless installation.  Runs on Mac, Linux, and Windows.
* [ansible-role-paperless](https://github.com/ovv/ansible-role-paperless): An easy way to get Paperless running via Ansible.
* [paperless-cli](https://github.com/stgarf/paperless-cli): A golang command line binary to interact with a Paperless instance.

# Important Note

Document scanners are typically used to scan sensitive documents.  Things like your social insurance number, tax records, invoices, etc.  Everything is stored in the clear without encryption by default (it needs to be searchable, so if someone has ideas on how to do that on encrypted data, I'm all ears).  This means that Paperless should never be run on an untrusted host.  Instead, I recommend that if you do want to use it, run it locally on a server in your own home.
