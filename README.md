[![Build Status](https://travis-ci.org/jonaswinkler/paperless-ng.svg?branch=master)](https://travis-ci.org/jonaswinkler/paperless-ng)
[![Documentation Status](https://readthedocs.org/projects/paperless-ng/badge/?version=latest)](https://paperless-ng.readthedocs.io/en/latest/?badge=latest)
[![Docker Hub Pulls](https://img.shields.io/docker/pulls/jonaswinkler/paperless-ng.svg)](https://hub.docker.com/r/jonaswinkler/paperless-ng)
[![Coverage Status](https://coveralls.io/repos/github/jonaswinkler/paperless-ng/badge.svg?branch=master)](https://coveralls.io/github/jonaswinkler/paperless-ng?branch=master)

# Paperless-ng

[Paperless](https://github.com/the-paperless-project/paperless) is an application by Daniel Quinn and others that indexes your scanned documents and allows you to easily search for documents and store metadata alongside your documents.

Paperless-ng is a fork of the original project, adding a new interface and many other changes under the hood. For a detailed list of changes, see below.

This project is still in development and some things may not work as expected.

# How it Works

Paperless does not control your scanner, it only helps you deal with what your scanner produces.

1. Buy a document scanner that can write to a place on your network.  If you need some inspiration, have a look at the [scanner recommendations](https://paperless.readthedocs.io/en/latest/scanners.html) page.
2. Set it up to "scan to FTP" or something similar. It should be able to push scanned images to a server without you having to do anything.  Of course if your scanner doesn't know how to automatically upload the file somewhere, you can always do that manually. Paperless doesn't care how the documents get into its local consumption directory.
3. Have the target server run the Paperless consumption script to OCR the file and index it into a local database.
4. Use the web frontend to sift through the database and find what you want.
5. Download the PDF you need/want via the web interface and do whatever you like with it.  You can even print it and send it as if it's the original. In most cases, no one will care or notice.

Here's what you get:

![The before and after](https://raw.githubusercontent.com/the-paperless-project/paperless/master/docs/_static/screenshot.png)

# Why Paperless-ng?

I wanted to make big changes to the project that will impact the way it is used by its users greatly. Among the users who currently use paperless in production there are probably many that don't want these changes right away. I also wanted to have more control over what goes into the code and what does not. Therefore, paperless-ng was created. NG stands for both Angular (the framework used for the Frontend) and next-gen. Publishing this project under a different name also avoids confusion between paperless and paperless-ng.

The gist of the changes is the following:

* New front end. This will eventually be mobile friendly as well.
* New full text search.
* Machine learning powered document matching.
* Code cleanup in many, MANY areas.

If you want to see some screenshots of paperless-ng in action, [some are available in the documentation](https://paperless-ng.readthedocs.io/en/latest/screenshots.html).

For a complete list of changes, check out the [changelog](https://paperless-ng.readthedocs.io/en/latest/changelog.html)

## Planned

These features will make it into the application at some point, sorted by priority.

- **More search.** The search backend is incredibly versatile and customizable. Searching is the most important feature of this project and thus, I want to implement things like:
  - Group and limit search results by correspondent, show “more from this” links in the results.
  - Ability to search for “Similar documents” in the search results
  - Provide corrections for mispelled queries
- **More robust consumer** that shows its progress on the web page.
- **More rigid email processing**. Like, dont delete imported mail, provide filters, etc...
- **Arbitrary tag colors**. Allow the selection of any color with a color picker.

## On the chopping block.

I don't know if these features are used all that much. I don't exactly know how they work and will probably remove them at some point in the future.

- **GnuPG encrypion.** Since its disabled by default and the website allows transparent access to encrypted documents anyway, this doesn’t really provide any benefit over having the application stored on an encrypted file system.

# Getting started

The recommended way to deploy paperless is docker-compose. Use the provided docker-compose.yml files to get started. This pulls the image from Docker hub. Alternatively, you can build the image yourself.

Read the [documentation](https://paperless-ng.readthedocs.io/en/latest/setup.html#installation) on how to get started.

Alternatively, you can install the dependencies and setup apache and a database server yourself. Details for that will be available in the documentation.

# Migrating to paperless-ng

Read the section about [migration](https://paperless-ng.readthedocs.io/en/latest/setup.html#migration-to-paperless-ng) in the documentation.

# Documentation

The documentation for Paperless-ng is available on [ReadTheDocs](https://paperless-ng.readthedocs.io/).

# Affiliated Projects

Paperless has been around a while now, and people are starting to build stuff on top of it.  If you're one of those people, we can add your project to this list:

* [Paperless App](https://github.com/bauerj/paperless_app): An Android/iOS app for Paperless.
* [Paperless Desktop](https://github.com/thomasbrueggemann/paperless-desktop): A desktop UI for your Paperless installation.  Runs on Mac, Linux, and Windows.
* [ansible-role-paperless](https://github.com/ovv/ansible-role-paperless): An easy way to get Paperless running via Ansible.
* [paperless-cli](https://github.com/stgarf/paperless-cli): A golang command line binary to interact with a Paperless instance.

Compatibility with Paperless-ng is unknown.

# Important Note

Document scanners are typically used to scan sensitive documents.  Things like your social insurance number, tax records, invoices, etc.  Everything is stored in the clear without encryption by default (it needs to be searchable, so if someone has ideas on how to do that on encrypted data, I'm all ears).  This means that Paperless should never be run on an untrusted host.  Instead, I recommend that if you do want to use it, run it locally on a server in your own home.
