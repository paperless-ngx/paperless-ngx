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

This is a list of changes that have been made to the original project.

## Added
- **A new single page UI** built with bootstrap and Angular. Its much more responsive than the django admin pages. It features the follwing improvements over the old django admin interface:
  - *Dashboard.* The landing page shows some useful information, such as statistics, recently scanned documents, file uploading, and possibly more in the future.
  - *Document uploading on the web page.* This is very crude right now, but gets the job done. It simply uploads the documents and stores them in the configured consumer directory. The API for that has always been in the project, there simply was no form on the UI to support it.
  - *Full text search* with a proper document indexer: The search feature sorts documents by relevance to the search query, highlights query terms in the found documents and provides autocomplete while typing the query. This is still very basic but will see extensions in the future.
  - *Saveable filters.* Save filter and sorting presets and optionally display a couple documents of saved filters (i.e., your inbox sorted descending by added date, or tagged TODO, oldest to newest) on the dash board.
  - *Statistics.* Provides basic statistics about your document collection.
- **Document types.** Similar to correspondents, each document may have a type (i.e., invoice, letter, receipt, bank statement, ...). I've initially intented to use this for some individual processing of differently typed documents, however, no such features exists yet.
- **Inbox tags.** These tags are automatically assigned to every newly scanned document. They are intented to be removed once you have manually edited the meta data of a document.
- **Automatic matching** for document types, correspondents, and tags. A new matching algorithm has been implemented (Auto), which is based on a classification model (simple feed forward neural nets are used). This classifier is trained on your document collection and learns to assign metadata to new documents based on their similiarity to existing documents.
  - If, for example, all your bank statements for a specific account are tagged with "bank_account_1234" and the matching algorithm of that tag is set to Auto, the classifier learns relevant phrases and words in the documents and assigns this tag automatically to newly scanned and matching documents.
  - This works reasonably well, if there is a correlation between the tag and the content of the document. Tags such as 'TODO' or 'Contact Correspondent' cannot be assigned automatically.
- **Archive serial numbers.** These are there to support the recommended workflow for storing physical copies of very important documents. The idea is that if a document has to be kept in physical form, you write a running number on the document before scanning (the archive serial number) and keep these documents sorted by number in a binder. If you need to access a specific physical document at some point in time, search for the document in paperless, identify the ASN and grab the document.

## Modified
- **(BREAKING) REST API changes.** In order to support the new UI, changes had to be made to the API. Some filters are not available anymore, other filters were added. Furthermore, foreign key relationships are not expressed with URLs anymore, but with their respective ids. Also, the urls for fetching documents and thumbnails have changed. Redirects are in place to support the old urls.

## Internal changes
- Many improvements to the code. More concise logging of the consumer, better multithreading of the tesseract parser for large documents, less hacks overall.
- Updated docker image. This image runs everything in a single container. (Except the optional database, of course)

## Removed

These features were removed each due to two reasons. First, I did not feel these features contributed all that much to the over project, and second, I don't want to maintain these features.

- **(BREAKING) Reminders.** I have no idea what they were used for and thus removed them from the project.
- **Every customization made to the admin interface.** Since this is not the primary interface for the application anymore, there is no need to keep and maintain these. Besides, some changes were incompatible with the most recent versions of django. The interface is completely usable, though.

## Planned

These features will make it into the application at some point, sorted by priority.

- **More search.** The search backend is incredibly versatile and customizable. Searching is the most important feature of this project and thus, I want to implement things like:
  - Group and limit search results by correspondent, show “more from this” links in the results.
  - Ability to search for “Similar documents” in the search results
  - Provide corrections for mispelled queries
- **More robust consumer** that shows its progress on the web page.
- **Arbitrary tag colors**. Allow the selection of any color with a color picker.

## On the chopping block.

I don't know if these features are used all that much. I don't exactly know how they work and will probably remove them at some point in the future.

- **GnuPG encrypion.** Since its disabled by default and the website allows transparent access to encrypted documents anyway, this doesn’t really provide any benefit over having the application stored on an encrypted file system.
- **E-Mail scanning.** I don’t use it and don’t know the state of the implementation. I’ll have to look into that.

# Getting started

The recommended way to deploy paperless is docker-compose.

    git clone https://github.com/jonaswinkler/paperless
    cd paperless
    cp docker-compose.yml.example docker-compose.yml
    cp docker-compose.env.example docker-compose.env
    docker-compose up -d

Please be aware that this uses a postgres database instead of sqlite. If you want to continue using sqlite, remove the database-related options from the docker-compose.env file.

Alternatively, you can install the dependencies and setup apache and a database server yourself. Details for that will be available in the documentation.

# Migrating to paperless-ng

Don't do it yet. The migrations are in place, but I have not verified yet that they work.

# Documentation

The documentation for Paperless is available on [ReadTheDocs](https://paperless-ng.readthedocs.io/). Updated documentation for this project is not yet available.

# Affiliated Projects

Paperless has been around a while now, and people are starting to build stuff on top of it.  If you're one of those people, we can add your project to this list:

* [Paperless App](https://github.com/bauerj/paperless_app): An Android/iOS app for Paperless. This app is not compatible at this point.
* [Paperless Desktop](https://github.com/thomasbrueggemann/paperless-desktop): A desktop UI for your Paperless installation.  Runs on Mac, Linux, and Windows.
* [ansible-role-paperless](https://github.com/ovv/ansible-role-paperless): An easy way to get Paperless running via Ansible.
* [paperless-cli](https://github.com/stgarf/paperless-cli): A golang command line binary to interact with a Paperless instance.

# Important Note

Document scanners are typically used to scan sensitive documents.  Things like your social insurance number, tax records, invoices, etc.  Everything is stored in the clear without encryption by default (it needs to be searchable, so if someone has ideas on how to do that on encrypted data, I'm all ears).  This means that Paperless should never be run on an untrusted host.  Instead, I recommend that if you do want to use it, run it locally on a server in your own home.
