
.. _paperless_changelog:

*********
Changelog
*********

paperless-ng 1.5.0
##################

Support for Python 3.6 was dropped.

* Updated python dependencies.
* Base image of the docker image changed from Debian Buster to Debian Bullseye due to its recent release.
* The docker image now uses python 3.9.
* Added the Luxembourgish locale. Thanks for translating!
* `Daniel Albers`_ added support for making the files and folders ignored by the paperless consume folder scanner configurable. See ``PAPERLESS_CONSUMER_IGNORE_PATTERNS``.

paperless-ng 1.4.5
##################

This is a maintenance release.

* Updated Python and Angular dependencies.
* Changed the algorithm that changes permissions during startup. This is still fast,
  and will hopefully cause less issues.
* Fixed an issue that would sometimes cause paperless to write an incomplete
  classification model file to disk.
* Fixed an issue with the OCRmyPDF parser that would always try to extract text
  with PDFminer even from non-PDF files.

paperless-ng 1.4.4
##################

* Drastically decreased the startup time of the docker container. The startup script adjusts file permissions of all data only if changes are required.
* Paperless mail: Added ability to specify the character set for each server.
* Document consumption: Ignore Mac OS specific files such as ``.DS_STORE`` and ``._XXXXX.pdf``.
* Fixed an issue with the automatic matching algorithm that prevents paperless from consuming new files.
* Updated translations.

paperless-ng 1.4.3
##################

* Additions and changes

  * Added Swedish locale.
  * `Stéphane Brunner`_ added an option to disable the progress bars of all management commands.
  * `Jo Vandeginste`_ added support for RTF documents to the Apache TIKA parser.
  * `Michael Shamoon`_ added dark mode for the login and logout pages.
  * `Alexander Menk`_ added additional stylesheets for printing. You can now print any page of paperless and the print result will hide the page header, sidebar, and action buttons.
  * Added support for sorting when using full text search.

* Fixes

  * `puuu`_ fixed ``PAPERLESS_FORCE_SCRIPT_NAME``. You can now host paperless on sub paths such as ``https://localhost:8000/paperless/``.
  * Fixed an issue with the document consumer crashing on certain documents due to issues with pdfminer.six. This library is used for PDF text extraction.

paperless-ng 1.4.2
##################

* Fixed an issue with ``sudo`` that caused paperless to not start on many Raspberry Pi devices. Thank you `WhiteHatTux`_!

paperless-ng 1.4.1
##################

* Added Polish locale.

* Changed some parts of the Dockerfile to hopefully restore functionality on certain ARM devices.

* Updated python dependencies.

* `Michael Shamoon`_ added a sticky filter / bulk edit bar.

* `sbrl`_ changed the docker-entrypoint.sh script to increase compatibility with NFS shares.

* `Chris Nagy`_ added support for creating a super user by passing ``PAPERLESS_ADMIN_USER`` and
  ``PAPERLESS_ADMIN_PASSWORD`` as environment variables to the docker container.

paperless-ng 1.4.0
##################

* Docker images now use tesseract 4.1.1, which should fix a series of issues with OCR.

* The full text search now displays results using the default document list. This enables
  selection, filtering and bulk edit on search results.

* Changes

  * Firefox only: Highlight search query in PDF previews.

  * New URL pattern for accessing documents by ASN directly (http://<paperless>/asn/123)

  * Added logging when executing pre- and post-consume scripts.

  * Better error logging during document consumption.

  * Updated python dependencies.

  * Automatically inserts typed text when opening "Create new" dialogs on the document details page.

* Fixes

  * Fixed an issue with null characters in the document content.

.. note::

  The changed to the full text searching require you to reindex your documents.
  *The docker image does this automatically, you don't need to do anything.*
  To do this, execute the ``document_index reindex`` management command
  (see :ref:`administration-index`).

paperless-ng 1.3.2
##################

* Added translation into Portuguese.

* Changes

  * The exporter now exports user accounts, mail accounts, mail rules and saved views as well.

* Fixes

  * Minor layout issues with document cards and the log viewer.

  * Fixed an issue with any/all/exact matching when characters used in regular expressions were used for the match.

paperless-ng 1.3.1
##################

* Added translation into Spanish and Russian.

* Other changes

  * ISO-8601 date format will now always show years with 4 digits.

  * Added the ability to search for a document with a specific ASN.

  * The document cards now display ASN, types and dates in a more organized way.

  * Added document previews when hovering over the preview button.

* Fixes

  * The startup check for write permissions now works properly on NFS shares.

  * Fixed an issue with the search results score indicator.

  * Paperless was unable to generate thumbnails for encrypted PDF files and failed. Paperless will now generate a default thumbnail for these files.

  * Fixed ``AUTO_LOGIN_USERNAME``: Unable to perform POST/PUT/DELETE requests and unable to receive WebSocket messages.

paperless-ng 1.3.0
##################

This release contains new database migrations.

* Changes

  * The REST API is versioned from this point onwards. This will allow me to make changes without breaking existing clients. See the documentation about :ref:`api-versioning` for details.

  * Added a color picker for tag colors.

  * Added the ability to use the filter for searching the document content as well.

  * Added translations into Italian and Romanian. Thank you!

  * Close individual documents from the sidebar. Thanks to `Michael Shamoon`_.

  * `BolkoSchreiber <https://github.com/BolkoSchreiber>`_ added an option to disable/enable thumbnail inversion in dark mode.

  * `Simon Taddiken <https://github.com/skuzzle>`_ added the ability to customize the header used for remote user authentication with SSO applications.

* Bug fixes

  * Fixed an issue with the auto matching algorithm when more than 256 tags were used.


paperless-ng 1.2.1
##################

* `Rodrigo Avelino <https://github.com/rodavelino>`_ translated Paperless into Portuguese (Brazil)!

* The date input fields now respect the currently selected date format.

* Added a fancy icon when adding paperless to the home screen on iOS devices. Thanks to `Joel Nordell <https://github.com/joelnordell>`_.

* When using regular expression matching, the regular expression is now validated before saving the tag/correspondent/type.

* Regression fix: Dates on the front end did not respect date locale settings in some cases.

paperless-ng 1.2.0
##################

* Changes to the OCRmyPDF integration

  * Added support for deskewing and automatic rotation of incorrectly rotated pages. This is enabled by default, see :ref:`configuration-ocr`.
  * Better support for encrypted files.
  * Better support for various other PDF files: Paperless will now attempt to force OCR with safe options when OCR fails with the configured options.
  * Added an explicit option to skip cleaning with ``unpaper``.

* Download multiple selected documents as a zip archive.

* The document list now remembers the current page.

* Improved responsiveness when switching between saved views and the document list.

* Increased the default wait time when observing files in the consumption folder
  with polling from 1 to 5 seconds. This will decrease the likelihood of paperless
  consuming partially written files.

* Fixed a crash of the document archiver management command when trying to process documents with unknown mime types.

* Paperless no longer depends on ``libpoppler-cpp-dev``.

paperless-ng 1.1.4
##################

* Added English (GB) locale.

* Added ISO-8601 date display option.

paperless-ng 1.1.3
##################

* Added a docker-specific configuration option to adjust the number of
  worker processes of the web server. See :ref:`configuration-docker`.

* Some more memory usage optimizations.

* Don't show inbox statistics if no inbox tag is defined.

paperless-ng 1.1.2
##################

* Always show top left corner of thumbnails, even for extra wide documents.

* Added a management command for executing the sanity checker directly.
  See :ref:`utilities-sanity-checker`.

* The weekly sanity check now reports messages in the log files.

* Fixed an issue with the metadata tab not reporting anything in case of missing files.

* Reverted a change from 1.1.0 that caused huge memory usage due to redis caching.

* Some memory usage optimizations.

paperless-ng 1.1.1
##################

This release contains new database migrations.

* Fixed a bug in the sanity checker that would cause it to display "x not in list" errors instead of actual issues.

* Fixed a bug with filename generation for archive filenames that would cause the archive files of two documents to overlap.

  * This happened when ``PAPERLESS_FILENAME_FORMAT`` is used and the filenames of two or more documents are the same, except for the file extension.
  * Paperless will now store the archive filename in the database as well instead of deriving it from the original filename, and use the
    same logic for detecting and avoiding filename clashes that's also used for original filenames.
  * The migrations will repair any missing archive files. If you're using tika, ensure that tika is running while performing the migration. Docker-compose will take care of that.

* Fixed a bug with thumbnail regeneration when TIKA integration was used.

* Added ASN as a placeholder field to the filename format.

* The docker image now comes with built-in shortcuts for most management commands. These are now the recommended way to execute management commands, since these
  also ensure that they're always executed as the paperless user and you're less likely to run into permission issues. See :ref:`utilities-management-commands`.

paperless-ng 1.1.0
##################

* Document processing status

  * Paperless now shows the status of processing documents on the dashboard in real time.
  * Status notifications when

    * New documents are detected in the consumption folder, in mails, uploaded on the front end,
      or added with one of the mobile apps.
    * Documents are successfully added to paperless.
    * Document consumption failed (with error messages)

  * Configuration options to enable/disable individual notifications.

* Live updates to document lists and saved views when new documents are added.

  .. hint::

    For status notifications and live updates to work, paperless now requires an `ASGI <https://asgi.readthedocs.io/en/latest/>`_-enabled
    web server. The docker images uses ``gunicorn`` and an ASGI-enabled worker called `uvicorn <http://www.uvicorn.org/>`_,
    and there is no need to configure anything.

    For bare metal installations, changes are required for the notifications to work. Adapt the service ``paperless-webserver.service``
    to use the supplied ``gunicorn.conf.py`` configuration file and adapt the reference to the ASGI application as follows:

    .. code::

      ExecStart=/opt/paperless/.local/bin/gunicorn -c /opt/paperless/gunicorn.conf.py paperless.asgi:application

    Paperless will continue to work with WSGI, but you will not get any status notifications.

    Apache ``mod_wsgi`` users, see :ref:`this note <faq-mod_wsgi>`.

* Paperless now offers suggestions for tags, correspondents and types on the document detail page.

* Added an interactive easy install script that automatically downloads, configures and starts paperless with docker.

* Official support for Python 3.9.

* Other changes and fixes

  * Adjusted the default parallelization settings to run more than one task in parallel on systems with 4 or less cores.
    This addresses issues with paperless not consuming any new files when other tasks are running.

  * Fixed a rare race condition that would cause paperless to process incompletely written files when using the upload on the dashboard.

  * The document classifier no longer issues warnings and errors when auto matching is not used at all.

  * Better icon for document previews.

  * Better info section in the side bar.

  * Paperless no longer logs to the database. Instead, logs are written to rotating log files. This solves many "database is locked"
    issues on Raspberry Pi, especially when SQLite is used.

  * By default, log files are written to ``PAPERLESS_DATA_DIR/log/``. Logging settings can be adjusted with
    ``PAPERLESS_LOGGING_DIR``, ``PAPERLESS_LOGROTATE_MAX_SIZE`` and
    ``PAPERLESS_LOGROTATE_MAX_BACKUPS``.

paperless-ng 1.0.0
##################

Nothing special about this release, but since there are relatively few bug reports coming in, I think that this is reasonably stable.

* Document export

  * The document exporter has been rewritten to support updating an already existing export in place.
    This enables incremental backups with ``rsync``.
  * The document exporter supports naming exported files according to ``PAPERLESS_FILENAME_FORMAT``.
  * The document exporter locks the media directory and the database during execution to ensure that
    the resulting export is consistent.
  * See the :ref:`updated documentation <utilities-exporter>` for more details.

* Other changes and additions

  * Added a language selector to the settings.
  * Added date format options to the settings.
  * Range selection with shift clicking is now possible in the document list.
  * Filtering correspondent, type and tag management pages by name.
  * Focus "Name" field in dialogs by default.


paperless-ng 0.9.14
###################

Starting with this version, releases are getting built automatically. This release also comes with changes on how to install and
update paperless.

* Paperless now uses GitHub Actions to make releases and build docker images.

  * Docker images are available for amd64, armhf, and aarch64.
  * When you pull an image from Docker Hub, Docker will automatically select the correct image for you.

* Changes to docker installations and updates

  * The ``-dockerfiles.tar.xz`` release archive is gone. Instead, simply grab the docker files from ``/docker/compose`` in the repository
    if you wish to install paperless by pulling from the hub.
  * The docker compose files in ``/docker/compose`` were changed to always use the ``latest`` version automatically. In order to do further
    updates, simply do a ``docker-compose pull``. The documentation has been updated.
  * The docker compose files were changed to restart paperless on system boot only if it was running before shutdown.
  * Documentation of the docker-compose files about what they do.

* Changes to bare metal installations and updates

  * The release archive is built exactly like before. However, the release now comes with already compiled translation messages and
    collected static files. Therefore, the update steps ``compilemessages`` and ``collectstatic`` are now obsolete.

* Other changes

  * A new configuration option ``PAPERLESS_IGNORE_DATES`` was added by `jayme-github`_. This can be used to instruct paperless to ignore
    certain dates (such as your date of birth) when guessing the date from the document content. This was actually introduced in 0.9.12,
    I just forgot to mention it in the changelog.
  * The filter drop downs now display selected entries on top of all other entries.
  * The PostgreSQL client now supports setting an explicit ``sslmode`` to force encryption of the connection to PostgreSQL.
  * The docker images now come with ``jbig2enc``, which is a lossless image encoder for PDF documents and decreases the size of certain
    PDF/A documents.
  * When using any of the manual matching algorithms, paperless now logs messages about when and why these matching algorithms matched.
  * The default settings for parallelization in paperless were adjusted to always leave one CPU core free.
  * Added an option to the frontend to choose which method to use for displaying PDF documents.

* Fixes

  * An issue with the tika parser not picking up files from the consumption directory was fixed.
  * A couple changes to the dark mode and fixes to several other layout issues.
  * An issue with the drop downs for correspondents, tags and types not properly supporting filtering with special characters was fixed.
  * Fixed an issue with filenames of downloaded files: Dates where off by one day due to timezone issues.
  * Searching will continue to work even when the index returns non-existing documents. This resulted in "Document does not exist" errors
    before. Instead, a warning is logged, indicating the issue.
  * An issue with the consumer crashing when invalid regular expression were used was fixed.

paperless-ng 0.9.13
###################

* Fixed an issue with Paperless not starting due to the new Tika integration when ``USERMAP_UID`` and ``USERMAP_GID`` was used
  in the ``docker-compose.env`` file.

paperless-ng 0.9.12
###################

* Paperless localization

  * Thanks to the combined efforts of many users, Paperless is now available in English, Dutch, French and German.

* Thanks to `Jo Vandeginste`_, Paperless has optional support for Office documents such as .docx, .doc, .odt and more.

  * See the :ref:`configuration<configuration-tika>` on how to enable this feature. This feature requires two additional services
    (one for parsing Office documents and metadata extraction and another for converting Office documents to PDF), and is therefore
    not enabled on default installations.
  * As with all other documents, paperless converts Office documents to PDF and stores both the original as well as the archived PDF.

* Dark mode

  * Thanks to `Michael Shamoon`_, paperless now has a dark mode. Configuration is available in the settings.

* Other changes and additions

  * The PDF viewer now uses a local copy of some dependencies instead of fetching them from the internet. Thanks to `slorenz`_.
  * Revamped search bar styling thanks to `Michael Shamoon`_.
  * Sorting in the document list by clicking on table headers.
  * A button was added to the document detail page that assigns a new ASN to a document.
  * Form field validation: When providing invalid input in a form (such as a duplicate ASN or no name), paperless now has visual
    indicators and clearer error messages about what's wrong.
  * Paperless disables buttons with network actions (such as save and delete) when a network action is active. This indicates that
    something is happening and prevents double clicking.
  * When using "Save & next", the title field is focussed automatically to better support keyboard editing.
  * E-Mail: Added filter rule parameters to allow inline attachments (watch out for mails with inlined images!) and attachment filename filters
    with wildcards.
  * Support for remote user authentication thanks to `Michael Shamoon`_. This is useful for hiding Paperless behind single sign on applications
    such as `authelia <https://www.authelia.com/>`_.
  * "Clear filters" has been renamed to "Reset filters" and now correctly restores the default filters on saved views. Thanks to `Michael Shamoon`_

* Fixes

  * Paperless was unable to save views when "Not assigned" was chosen in one of the filter dropdowns.
  * Clearer error messages when pre and post consumption scripts do not exist.
  * The post consumption script is executed later in the consumption process. Before the change, an ID was passed to the script referring to
    a document that did not yet exist in the database.

paperless-ng 0.9.11
###################

* Fixed an issue with the docker image not starting at all due to a configuration change of the web server.


paperless-ng 0.9.10
###################

* Bulk editing

  * Thanks to `Michael Shamoon`_, we've got a new interface for the bulk editor.
  * There are some configuration options in the settings to alter the behavior.

* Other changes and additions

  * Thanks to `zjean`_, paperless now publishes a webmanifest, which is useful for adding the application to home screens on mobile devices.
  * The Paperless-ng logo now navigates to the dashboard.
  * Filter for documents that don't have any correspondents, types or tags assigned.
  * Tags, types and correspondents are now sorted case insensitive.
  * Lots of preparation work for localization support.

* Fixes

  * Added missing dependencies for Raspberry Pi builds.
  * Fixed an issue with plain text file consumption: Thumbnail generation failed due to missing fonts.
  * An issue with the search index reporting missing documents after bulk deletes was fixed.
  * Issue with the tag selector not clearing input correctly.
  * The consumer used to stop working when encountering an incomplete classifier model file.

.. note::

  The bulk delete operations did not update the search index. Therefore, documents that you deleted remained in the index and
  caused the search to return messages about missing documents when searching. Further bulk operations will properly update
  the index.

  However, this change is not retroactive: If you used the delete method of the bulk editor, you need to reindex your search index
  by :ref:`running the management command document_index with the argument reindex <administration-index>`.

paperless-ng 0.9.9
##################

Christmas release!

* Bulk editing

  * Paperless now supports bulk editing.
  * The following operations are available: Add and remove correspondents, tags, document types from selected documents, as well as mass-deleting documents.
  * We've got a more fancy UI in the works that makes these features more accessible, but that's not quite ready yet.

* Searching

  * Paperless now supports searching for similar documents ("More like this") both from the document detail page as well as from individual search results.
  * A search score indicates how well a document matches the search query, or how similar a document is to a given reference document.

* Other additions and changes

  * Clarification in the UI that the fields "Match" and "Is insensitive" are not relevant for the Auto matching algorithm.
  * New select interface for tags, types and correspondents allows filtering. This also improves tag selection. Thanks again to `Michael Shamoon`_!
  * Page navigation controls for the document viewer, thanks to `Michael Shamoon`_.
  * Layout changes to the small cards document list.
  * The dashboard now displays the username (or full name if specified in the admin) on the dashboard.

* Fixes

  * An error that caused the document importer to crash was fixed.
  * An issue with changes not being possible when ``PAPERLESS_COOKIE_PREFIX`` is used was fixed.
  * The date selection filters now allow manual entry of dates.

* Feature Removal

  * Most of the guesswork features have been removed. Paperless no longer tries to extract correspondents and tags from file names.

paperless-ng 0.9.8
##################

This release addresses two severe issues with the previous release.

* The delete buttons for document types, correspondents and tags were not working.
* The document section in the admin was causing internal server errors (500).


paperless-ng 0.9.7
##################


* Front end

  * Thanks to the hard work of `Michael Shamoon`_, paperless now comes with a much more streamlined UI for
    filtering documents.

  * `Michael Shamoon`_ replaced the document preview with another component. This should fix compatibility with Safari browsers.

  * Added buttons to the management pages to quickly show all documents with one specific tag, correspondent, or title.

  * Paperless now stores your saved views on the server and associates them with your user account.
    This means that you can access your views on multiple devices and have separate views for different users.
    You will have to recreate your views.

  * The GitHub and documentation links now open in new tabs/windows. Thanks to `rYR79435`_.

  * Paperless now generates default saved view names when saving views with certain filter rules.

  * Added a small version indicator to the front end.

* Other additions and changes

  * The new filename format field ``{tag_list}`` inserts a list of tags into the filename, separated by comma.
  * The ``document_retagger`` no longer removes inbox tags or tags without matching rules.
  * The new configuration option ``PAPERLESS_COOKIE_PREFIX`` allows you to run multiple instances of paperless on different ports.
    This option enables you to be logged in into multiple instances by specifying different cookie names for each instance.

* Fixes

  * Sometimes paperless would assign dates in the future to newly consumed documents.
  * The filename format fields ``{created_month}`` and ``{created_day}`` now use a leading zero for single digit values.
  * The filename format field ``{tags}`` can no longer be used without arguments.
  * Paperless was not able to consume many images (especially images from mobile scanners) due to missing DPI information.
    Paperless now assumes A4 paper size for PDF generation if no DPI information is present.
  * Documents with empty titles could not be opened from the table view due to the link being empty.
  * Fixed an issue with filenames containing special characters such as ``:`` not being accepted for upload.
  * Fixed issues with thumbnail generation for plain text files.


paperless-ng 0.9.6
##################

This release focusses primarily on many small issues with the UI.

* Front end

  * Paperless now has proper window titles.
  * Fixed an issue with the small cards when more than 7 tags were used.
  * Navigation of the "Show all" links adjusted. They navigate to the saved view now, if available in the sidebar.
  * Some indication on the document lists that a filter is active was added.
  * There's a new filter to filter for documents that do *not* have a certain tag.
  * The file upload box now shows upload progress.
  * The document edit page was reorganized.
  * The document edit page shows various information about a document.
  * An issue with the height of the preview was fixed.
  * Table issues with too long document titles fixed.

* API

  * The API now serves file names with documents.
  * The API now serves various metadata about documents.
  * API documentation updated.

* Other

  * Fixed an issue with the docker image when a non-standard PostgreSQL port was used.
  * The docker image was trying check for installed languages before actually installing them.
  * ``FILENAME_FORMAT`` placeholder for document types.
  * The filename formatter is now less restrictive with file names and tries to
    conserve the original correspondents, types and titles as much as possible.
  * The filename formatter does not include the document ID in filenames anymore. It will
    rather append ``_01``, ``_02``, etc when it detects duplicate filenames.

.. note::

  The changes to the filename format will apply to newly added documents and changed documents.
  If you want all files to reflect these changes, execute the ``document_renamer`` management
  command.


paperless-ng 0.9.5
##################

This release concludes the big changes I wanted to get rolled into paperless. The next releases before 1.0 will
focus on fixing issues, primarily.

* OCR

  * Paperless now uses `OCRmyPDF <https://github.com/jbarlow83/OCRmyPDF>`_ to perform OCR on documents.
    It still uses tesseract under the hood, but the PDF parser of Paperless has changed considerably and
    will behave different for some douments.
  * OCRmyPDF creates archived PDF/A documents with embedded text that can be selected in the front end.
  * Paperless stores archived versions of documents alongside with the originals. The originals can be
    accessed on the document edit page. If available, a dropdown menu will appear next to the download button.
  * Many of the configuration options regarding OCR have changed. See :ref:`configuration-ocr` for details.
  * Paperless no longer guesses the language of your documents. It always uses the language that you
    specified with ``PAPERLESS_OCR_LANGUAGE``. Be sure to set this to the language the majority of your
    documents are in. Multiple languages can be specified, but that requires more CPU time.
  * The management command :ref:`document_archiver <utilities-archiver>` can be used to create archived versions for already
    existing documents.

* Tags from consumption folder.

  * Thanks to `jayme-github`_, paperless now consumes files from sub folders in the consumption folder and is able to assign tags
    based on the sub folders a document was found in. This can be configured with ``PAPERLESS_CONSUMER_RECURSIVE`` and
    ``PAPERLESS_CONSUMER_SUBDIRS_AS_TAGS``.

* API

  * The API now offers token authentication.
  * The endpoint for uploading documents now supports specifying custom titles, correspondents, tags and types.
    This can be used by clients to override the default behavior of paperless. See :ref:`api-file_uploads`.
  * The document endpoint of API now serves documents in this form:

    * correspondents, document types and tags are referenced by their ID in the fields ``correspondent``, ``document_type`` and ``tags``. The ``*_id`` versions are gone. These fields are read/write.
    * paperless does not serve nested tags, correspondents or types anymore.

* Front end

  * Paperless does some basic caching of correspondents, tags and types and will only request them from the server when necessary or when entirely reloading the page.
  * Document list fetching is about 10%-30% faster now, especially when lots of tags/correspondents are present.
  * Some minor improvements to the front end, such as document count in the document list, better highlighting of the current page, and improvements to the filter behavior.

* Fixes:

  * A bug with the generation of filenames for files with unsupported types caused the exporter and
    document saving to crash.
  * Mail handling no longer exits entirely when encountering errors. It will skip the account/rule/message on which the error occured.
  * Assigning correspondents from mail sender names failed for very long names. Paperless no longer assigns correspondents in these cases.

paperless-ng 0.9.4
##################

* Searching:

  * Paperless now supports searching by tags, types and dates and correspondents. In order to have this applied to your
    existing documents, you need to perform a ``document_index reindex`` management command
    (see :ref:`administration-index`)
    that adds the data to the search index. You only need to do this once, since the schema of the search index changed.
    Paperless keeps the index updated after that whenever something changes.
  * Paperless now has spelling corrections ("Did you mean") for miss-typed queries.
  * The documentation contains :ref:`information about the query syntax <basic-searching>`.

* Front end:

  * Clickable tags, correspondents and types allow quick filtering for related documents.
  * Saved views are now editable.
  * Preview documents directly in the browser.
  * Navigation from the dashboard to saved views.

* Fixes:

  * A severe error when trying to use post consume scripts.
  * An error in the consumer that cause invalid messages of missing files to show up in the log.

* The documentation now contains information about bare metal installs and a section about
  how to setup the development environment.

paperless-ng 0.9.3
##################

* Setting ``PAPERLESS_AUTO_LOGIN_USERNAME`` replaces ``PAPERLESS_DISABLE_LOGIN``.
  You have to specify your username.
* Added a simple sanity checker that checks your documents for missing or orphaned files,
  files with wrong checksums, inaccessible files, and documents with empty content.
* It is no longer possible to encrypt your documents. For the time being, paperless will
  continue to operate with already encrypted documents.
* Fixes:

  * Paperless now uses inotify again, since the watchdog was causing issues which I was not
    aware of.
  * Issue with the automatic classifier not working with only one tag.
  * A couple issues with the search index being opened to eagerly.

* Added lots of tests for various parts of the application.

paperless-ng 0.9.2
##################

* Major changes to the front end (colors, logo, shadows, layout of the cards,
  better mobile support)

* Paperless now uses mime types and libmagic detection to determine
  if a file type is supported and which parser to use. Removes all
  file type checks that where present in MANY different places in
  paperless.

* Mail consumer now correctly consumes documents even when their
  content type was not set correctly. (i.e. PDF documents with
  content type ``application/octet-stream``)

* Basic sorting of mail rules added

* Much better admin for mail rule editing.

* Docker entrypoint script awaits the database server if it is
  configured.

* Disabled editing of logs.

* New setting ``PAPERLESS_OCR_PAGES`` limits the tesseract parser
  to the first n pages of scanned documents.

* Fixed a bug where tasks with too long task names would not show
  up in the admin.

paperless-ng 0.9.1
##################

* Moved documentation of the settings to the actual documentation.
* Updated release script to force the user to choose between SQLite
  and PostgreSQL. This avoids confusion when upgrading from paperless.


paperless-ng 0.9.0
##################

* **Deprecated:** GnuPG. :ref:`See this note on the state of GnuPG in paperless-ng. <utilities-encyption>`
  This features will most likely be removed in future versions.

* **Added:** New frontend. Features:

  * Single page application: It's much more responsive than the django admin pages.
  * Dashboard. Shows recently scanned documents, or todo notes, or other documents
    at wish. Allows uploading of documents. Shows basic statistics.
  * Better document list with multiple display options.
  * Full text search with result highlighting, auto completion and scoring based
    on the query. It uses a document search index in the background.
  * Saveable filters.
  * Better log viewer.

* **Added:** Document types. Assign these to documents just as correspondents.
  They may be used in the future to perform automatic operations on documents
  depending on the type.
* **Added:** Inbox tags. Define an inbox tag and it will automatically be
  assigned to any new document scanned into the system.
* **Added:** Automatic matching. A new matching algorithm that automatically
  assigns tags, document types and correspondents to your documents. It uses
  a neural network trained on your data.
* **Added:** Archive serial numbers. Assign these to quickly find documents stored in
  physical binders.
* **Added:** Enabled the internal user management of django. This isn't really a
  multi user solution, however, it allows more than one user to access the website
  and set some basic permissions / renew passwords.

* **Modified [breaking]:** All new mail consumer with customizable filters, actions and
  multiple account support. Replaces the old mail consumer. The new mail consumer
  needs different configuration but can be configured to act exactly like the old
  consumer.


* **Modified:** Changes to the consumer:

  * Now uses the excellent watchdog library that should make sure files are
    discovered no matter what the platform is.
  * The consumer now uses a task scheduler to run consumption processes in parallel.
    This means that consuming many documents should be much faster on systems with
    many cores.
  * Concurrency is controlled with the new settings ``PAPERLESS_TASK_WORKERS``
    and ``PAPERLESS_THREADS_PER_WORKER``. See TODO for details on concurrency.
  * The consumer no longer blocks the database for extended periods of time.
  * An issue with tesseract running multiple threads per page and slowing down
    the consumer was fixed.

* **Modified [breaking]:** REST Api changes:

  * New filters added, other filters removed (case sensitive filters, slug filters)
  * Endpoints for thumbnails, previews and downloads replace the old ``/fetch/`` urls. Redirects are in place.
  * Endpoint for document uploads replaces the old ``/push`` url. Redirects are in place.
  * Foreign key relationships are now served as IDs, not as urls.

* **Modified [breaking]:** PostgreSQL:

  * If ``PAPERLESS_DBHOST`` is specified in the settings, paperless uses PostgreSQL instead of SQLite.
    Username, database and password all default to ``paperless`` if not specified.

* **Modified [breaking]:** document_retagger management command rework. See
  :ref:`utilities-retagger` for details. Replaces ``document_correspondents``
  management command.
* **Removed [breaking]:** Reminders.
* **Removed:** All customizations made to the django admin pages.
* **Removed [breaking]:** The docker image no longer supports SSL. If you want to expose
  paperless to the internet, hide paperless behind a proxy server that handles SSL
  requests.
* **Internal changes:** Mostly code cleanup, including:

  * Rework of the code of the tesseract parser. This is now a lot cleaner.
  * Rework of the filename handling code. It was a mess.
  * Fixed some issues with the document exporter not exporting all documents when encountering duplicate filenames.
  * Added a task scheduler that takes care of checking mail, training the classifier, maintaining the document search index
    and consuming documents.
  * Updated dependencies. Now uses Pipenv all around.
  * Updated Dockerfile and docker-compose. Now uses ``supervisord`` to run everything paperless-related in a single container.

* **Settings:**

  * ``PAPERLESS_FORGIVING_OCR`` is now default and gone. Reason: Even if ``langdetect`` fails to detect
    a language, tesseract still does a very good job at ocr'ing a document with the default language.
    Certain language specifics such as umlauts may not get picked up properly.
  * ``PAPERLESS_DEBUG`` defaults to ``false``.
  * The presence of ``PAPERLESS_DBHOST`` now determines whether to use PostgreSQL or
    SQLite.
  * ``PAPERLESS_OCR_THREADS`` is gone and replaced with ``PAPERLESS_TASK_WORKERS`` and
    ``PAPERLESS_THREADS_PER_WORKER``. Refer to the config example for details.
  * ``PAPERLESS_OPTIMIZE_THUMBNAILS`` allows you to disable or enable thumbnail
    optimization. This is useful on less powerful devices.

* Many more small changes here and there. The usual stuff.

Paperless
#########

2.7.0
=====

* `syntonym`_ submitted a pull request to catch IMAP connection errors `#475`_.
* `Stéphane Brunner`_ added ``psycopg2`` to the Pipfile `#489`_.  He also fixed
  a syntax error in ``docker-compose.yml.example`` `#488`_ and added `DjangoQL`_,
  which allows a litany of handy search functionality `#492`_.
* `CkuT`_ and `JOKer`_ hacked out a simple, but super-helpful optimisation to
  how the thumbnails are served up, improving performance considerably `#481`_.
* `tsia`_ added a few fields to the tags REST API. `#483`_.
* `Brian Cribbs`_ improved the documentation to help people using Paperless
  over NFS `#484`_.
* `Brendan M. Sleight`_ updated the documentation to include a note for setting the
  ``DEBUG`` value.  The ``paperless.conf.example`` file was also updated to
  mirror the project defaults.


2.6.1
=====

* We now have a logo, complete with a favicon :-)
* Removed some problematic tests.
* Fix the docker-compose example config to include a shared consume volume so
  that using the push API will work for users of the Docker install.  Thanks to
  `Colin Frei`_ for fixing this in `#466`_.
* `khrise`_ submitted a pull request to include the ``added`` property to the
  REST API `#471`_.


2.6.0
=====

* Allow an infinite number of logs to be deleted.  Thanks to `Ulli`_ for noting
  the problem in `#433`_.
* Fix the ``RecentCorrespondentsFilter`` correspondents filter that was added
  in 2.4 to play nice with the defaults.  Thanks to `tsia`_ and `Sblop`_ who
  pointed this out. `#423`_.
* Updated dependencies to include (among other things) a security patch to
  requests.
* Fix text in sample data for tests so that the language guesser stops thinking
  that everything is in Catalan because we had *Lorem ipsum* in there.
* Tweaked the gunicorn sample command to use filesystem paths instead of Python
  paths. `#441`_
* Added pretty colour boxes next to the hex values in the Tags section, thanks
  to a pull request from `Joshua Taillon`_ `#442`_.
* Added a ``.editorconfig`` file to better specify coding style.
* `Joshua Taillon`_ also added some logic to tie Paperless' date guessing logic
  into how it parses file names on import. `#440`_


2.5.0
=====

* **New dependency**: Paperless now optimises thumbnail generation with
  `optipng`_, so you'll need to install that somewhere in your PATH or declare
  its location in ``PAPERLESS_OPTIPNG_BINARY``.  The Docker image has already
  been updated on the Docker Hub, so you just need to pull the latest one from
  there if you're a Docker user.

* "Login free" instances of Paperless were breaking whenever you tried to edit
  objects in the admin: adding/deleting tags or correspondents, or even fixing
  spelling.  This was due to the "user hack" we were applying to sessions that
  weren't using a login, as that hack user didn't have a valid id.  The fix was
  to attribute the first user id in the system to this hack user.  `#394`_

* A problem in how we handle slug values on Tags and Correspondents required a
  few changes to how we handle this field `#393`_:

  1. Slugs are no longer editable.  They're derived from the name of the tag or
     correspondent at save time, so if you wanna change the slug, you have to
     change the name, and even then you're restricted to the rules of the
     ``slugify()`` function.  The slug value is still visible in the admin
     though.
  2. I've added a migration to go over all existing tags & correspondents and
     rewrite the ``.slug`` values to ones conforming to the ``slugify()``
     rules.
  3. The consumption process now uses the same rules as ``.save()`` in
     determining a slug and using that to check for an existing
     tag/correspondent.

* An annoying bug in the date capture code was causing some bogus dates to be
  attached to documents, which in turn busted the UI.  Thanks to `Andrew Peng`_
  for reporting this. `#414`_.

* A bug in the Dockerfile meant that Tesseract language files weren't being
  installed correctly.  `euri10`_ was quick to provide a fix: `#406`_, `#413`_.

* Document consumption is now wrapped in a transaction as per an old ticket
  `#262`_.

* The ``get_date()`` functionality of the parsers has been consolidated onto
  the ``DocumentParser`` class since much of that code was redundant anyway.


2.4.0
=====

* A new set of actions are now available thanks to `jonaswinkler`_'s very first
  pull request!  You can now do nifty things like tag documents in bulk, or set
  correspondents in bulk.  `#405`_
* The import/export system is now a little smarter.  By default, documents are
  tagged as ``unencrypted``, since exports are by their nature unencrypted.
  It's now in the import step that we decide the storage type.  This allows you
  to export from an encrypted system and import into an unencrypted one, or
  vice-versa.
* The migration history has been slightly modified to accommodate PostgreSQL
  users.  Additionally, you can now tell paperless to use PostgreSQL simply by
  declaring ``PAPERLESS_DBUSER`` in your environment.  This will attempt to
  connect to your Postgres database without a password unless you also set
  ``PAPERLESS_DBPASS``.
* A bug was found in the REST API filter system that was the result of an
  update of django-filter some time ago.  This has now been patched in `#412`_.
  Thanks to `thepill`_ for spotting it!


2.3.0
=====

* Support for consuming plain text & markdown documents was added by
  `Joshua Taillon`_!  This was a long-requested feature, and it's addition is
  likely to be greatly appreciated by the community: `#395`_  Thanks also to
  `David Martin`_ for his assistance on the issue.
* `dubit0`_ found & fixed a bug that prevented management commands from running
  before we had an operational database: `#396`_
* Joshua also added a simple update to the thumbnail generation process to
  improve performance: `#399`_
* As his last bit of effort on this release, Joshua also added some code to
  allow you to view the documents inline rather than download them as an
  attachment. `#400`_
* Finally, `ahyear`_ found a slip in the Docker documentation and patched it.
  `#401`_


2.2.1
=====

* `Kyle Lucy`_ reported a bug quickly after the release of 2.2.0 where we broke
  the ``DISABLE_LOGIN`` feature: `#392`_.


2.2.0
=====

* Thanks to `dadosch`_, `Wolfgang Mader`_, and `Tim Brooks`_ this is the first
  version of Paperless that supports Django 2.0!  As a result of their hard
  work, you can now also run Paperless on Python 3.7 as well: `#386`_ &
  `#390`_.
* `Stéphane Brunner`_ added a few lines of code that made tagging interface a
  lot easier on those of us with lots of different tags: `#391`_.
* `Kilian Koeltzsch`_ noticed a bug in how we capture & automatically create
  tags, so that's fixed now too: `#384`_.
* `erikarvstedt`_ tweaked the behaviour of the test suite to be better behaved
  for packaging environments: `#383`_.
* `Lukasz Soluch`_ added CORS support to make building a new Javascript-based
  front-end cleaner & easier: `#387`_.


2.1.0
=====

* `Enno Lohmeier`_ added three simple features that make Paperless a lot more
  user (and developer) friendly:

  1. There's a new search box on the front page: `#374`_.
  2. The correspondents & tags pages now have a column showing the number of
     relevant documents: `#375`_.
  3. The Dockerfile has been tweaked to build faster for those of us who are
     doing active development on Paperless using the Docker environment:
     `#376`_.

* You now also have the ability to customise the interface to your heart's
  content by creating a file called ``overrides.css`` and/or ``overrides.js``
  in the root of your media directory.  Thanks to `Mark McFate`_ for this
  idea: `#371`_


2.0.0
=====

This is a big release as we've changed a core-functionality of Paperless: we no
longer encrypt files with GPG by default.

The reasons for this are many, but it boils down to that the encryption wasn't
really all that useful, as files on-disk were still accessible so long as you
had the key, and the key was most typically stored in the config file.  In
other words, your files are only as safe as the ``paperless`` user is.  In
addition to that, *the contents of the documents were never encrypted*, so
important numbers etc. were always accessible simply by querying the database.
Still, it was better than nothing, but the consensus from users appears to be
that it was more an annoyance than anything else, so this feature is now turned
off unless you explicitly set a passphrase in your config file.

Migrating from 1.x
==================

Encryption isn't gone, it's just off for new users.  So long as you have
``PAPERLESS_PASSPHRASE`` set in your config or your environment, Paperless
should continue to operate as it always has.  If however, you want to drop
encryption too, you only need to do two things:

1. Run ``./manage.py migrate && ./manage.py change_storage_type gpg unencrypted``.
   This will go through your entire database and Decrypt  All The Things.
2. Remove ``PAPERLESS_PASSPHRASE`` from your ``paperless.conf`` file, or simply
   stop declaring it in your environment.

Special thanks to `erikarvstedt`_, `matthewmoto`_, and `mcronce`_ who did the
bulk of the work on this big change.

1.4.0
=====

* `Quentin Dawans`_ has refactored the document consumer to allow for some
  command-line options.  Notably, you can now direct it to consume from a
  particular ``--directory``, limit the ``--loop-time``, set the time between
  mail server checks with ``--mail-delta`` or just run it as a one-off with
  ``--one-shot``.  See `#305`_ & `#313`_ for more information.
* Refactor the use of travis/tox/pytest/coverage into two files:
  ``.travis.yml`` and ``setup.cfg``.
* Start generating requirements.txt from a Pipfile.  I'll probably switch over
  to just using pipenv in the future.
* All for a alternative FreeBSD-friendly location for ``paperless.conf``.
  Thanks to `Martin Arendtsen`_ who provided this (`#322`_).
* Document consumption events are now logged in the Django admin events log.
  Thanks to `CkuT`_ for doing the legwork on this one and to `Quentin Dawans`_
  & `David Martin`_ for helping to coordinate & work out how the feature would
  be developed.
* `erikarvstedt`_ contributed a pull request (`#328`_) to add ``--noreload``
  to the default server start process.  This helps reduce the load imposed
  by the running webservice.
* Through some discussion on `#253`_ and `#323`_, we've removed a few of the
  hardcoded URL values to make it easier for people to host Paperless on a
  subdirectory.  Thanks to `Quentin Dawans`_ and `Kyle Lucy`_ for helping to
  work this out.
* The clickable area for documents on the listing page has been increased to a
  more predictable space thanks to a glorious hack from `erikarvstedt`_ in
  `#344`_.
* `Strubbl`_ noticed an annoying bug in the bash script wrapping the Docker
  entrypoint and fixed it with some very creating Bash skills: `#352`_.
* You can now use the search field to find documents by tag thanks to
  `thinkjk`_'s *first ever issue*: `#354`_.
* Inotify is now being used to detect additions to the consume directory thanks
  to some excellent work from `erikarvstedt`_ on `#351`_

1.3.0
=====

* You can now run Paperless without a login, though you'll still have to create
  at least one user.  This is thanks to a pull-request from `matthewmoto`_:
  `#295`_.  Note that logins are still required by default, and that you need
  to disable them by setting ``PAPERLESS_DISABLE_LOGIN="true"`` in your
  environment or in ``/etc/paperless.conf``.
* Fix for `#303`_ where sketchily-formatted documents could cause the consumer
  to break and insert half-records into the database breaking all sorts of
  things.  We now capture the return codes of both ``convert`` and ``unpaper``
  and fail-out nicely.
* Fix for additional date types thanks to input from `Isaac`_ and code from
  `BastianPoe`_ (`#301`_).
* Fix for running migrations in the Docker container (`#299`_).  Thanks to
  `Georgi Todorov`_ for the fix (`#300`_) and to `Pit`_ for the review.
* Fix for Docker cases where the issuing user is not UID 1000.  This was a
  collaborative fix between `Jeffrey Portman`_ and `Pit`_ in `#311`_ and
  `#312`_ to fix `#306`_.
* Patch the historical migrations to support MySQL's um, *interesting* way of
  handing indexes (`#308`_).  Thanks to `Simon Taddiken`_ for reporting the
  problem and helping me find where to fix it.

1.2.0
=====

* New Docker image, now based on Alpine, thanks to the efforts of `addadi`_
  and `Pit`_.  This new image is dramatically smaller than the Debian-based
  one, and it also has `a new home on Docker Hub`_.  A proper thank-you to
  `Pit`_ for hosting the image on his Docker account all this time, but after
  some discussion, we decided the image needed a more *official-looking* home.
* `BastianPoe`_ has added the long-awaited feature to automatically skip the
  OCR step when the PDF already contains text. This can be overridden by
  setting ``PAPERLESS_OCR_ALWAYS=YES`` either in your ``paperless.conf`` or
  in the environment.  Note that this also means that Paperless now requires
  ``libpoppler-cpp-dev`` to be installed. **Important**: You'll need to run
  ``pip install -r requirements.txt`` after the usual ``git pull`` to
  properly update.
* `BastianPoe`_ has also contributed a monumental amount of work (`#291`_) to
  solving `#158`_: setting the document creation date based on finding a date
  in the document text.

1.1.0
=====

* Fix for `#283`_, a redirect bug which broke interactions with
  paperless-desktop.  Thanks to `chris-aeviator`_ for reporting it.
* Addition of an optional new financial year filter, courtesy of
  `David Martin`_ `#256`_
* Fixed a typo in how thumbnails were named in exports `#285`_, courtesy of
  `Dan Panzarella`_

1.0.0
=====

* Upgrade to Django 1.11.  **You'll need to run
  ``pip install -r requirements.txt`` after the usual ``git pull`` to
  properly update**.
* Replace the templatetag-based hack we had for document listing in favour of
  a slightly less ugly solution in the form of another template tag with less
  copypasta.
* Support for multi-word-matches for auto-tagging thanks to an excellent
  patch from `ishirav`_ `#277`_.
* Fixed a CSS bug reported by `Stefan Hagen`_ that caused an overlapping of
  the text and checkboxes under some resolutions `#272`_.
* Patched the Docker config to force the serving of static files.  Credit for
  this one goes to `dev-rke`_ via `#248`_.
* Fix file permissions during Docker start up thanks to `Pit`_ on `#268`_.
* Date fields in the admin are now expressed as HTML5 date fields thanks to
  `Lukas Winkler`_'s issue `#278`_

0.8.0
=====

* Paperless can now run in a subdirectory on a host (``/paperless``), rather
  than always running in the root (``/``) thanks to `maphy-psd`_'s work on
  `#255`_.

0.7.0
=====

* **Potentially breaking change**: As per `#235`_, Paperless will no longer
  automatically delete documents attached to correspondents when those
  correspondents are themselves deleted.  This was Django's default
  behaviour, but didn't make much sense in Paperless' case.  Thanks to
  `Thomas Brueggemann`_ and `David Martin`_ for their input on this one.
* Fix for `#232`_ wherein Paperless wasn't recognising ``.tif`` files
  properly.  Thanks to `ayounggun`_ for reporting this one and to
  `Kusti Skytén`_ for posting the correct solution in the Github issue.

0.6.0
=====

* Abandon the shared-secret trick we were using for the POST API in favour
  of BasicAuth or Django session.
* Fix the POST API so it actually works.  `#236`_
* **Breaking change**: We've dropped the use of ``PAPERLESS_SHARED_SECRET``
  as it was being used both for the API (now replaced with a normal auth)
  and form email polling.  Now that we're only using it for email, this
  variable has been renamed to ``PAPERLESS_EMAIL_SECRET``.  The old value
  will still work for a while, but you should change your config if you've
  been using the email polling feature.  Thanks to `Joshua Gilman`_ for all
  the help with this feature.

0.5.0
=====

* Support for fuzzy matching in the auto-tagger & auto-correspondent systems
  thanks to `Jake Gysland`_'s patch `#220`_.
* Modified the Dockerfile to prepare an export directory (`#212`_).  Thanks
  to combined efforts from `Pit`_ and `Strubbl`_ in working out the kinks on
  this one.
* Updated the import/export scripts to include support for thumbnails.  Big
  thanks to `CkuT`_ for finding this shortcoming and doing the work to get
  it fixed in `#224`_.
* All of the following changes are thanks to `David Martin`_:
  * Bumped the dependency on pyocr to 0.4.7 so new users can make use of
  Tesseract 4 if they so prefer (`#226`_).
  * Fixed a number of issues with the automated mail handler (`#227`_, `#228`_)
  * Amended the documentation for better handling of systemd service files (`#229`_)
  * Amended the Django Admin configuration to have nice headers (`#230`_)

0.4.1
=====

* Fix for `#206`_ wherein the pluggable parser didn't recognise files with
  all-caps suffixes like ``.PDF``

0.4.0
=====

* Introducing reminders.  See `#199`_ for more information, but the short
  explanation is that you can now attach simple notes & times to documents
  which are made available via the API.  Currently, the default API
  (basically just the Django admin) doesn't really make use of this, but
  `Thomas Brueggemann`_ over at `Paperless Desktop`_ has said that he would
  like to make use of this feature in his project.

0.3.6
=====

* Fix for `#200`_ (!!) where the API wasn't configured to allow updating the
  correspondent or the tags for a document.
* The ``content`` field is now optional, to allow for the edge case of a
  purely graphical document.
* You can no longer add documents via the admin.  This never worked in the
  first place, so all I've done here is remove the link to the broken form.
* The consumer code has been heavily refactored to support a pluggable
  interface.  Install a paperless consumer via pip and tell paperless about
  it with an environment variable, and you're good to go.  Proper
  documentation is on its way.

0.3.5
=====

* A serious facelift for the documents listing page wherein we drop the
  tabular layout in favour of a tiled interface.
* Users can now configure the number of items per page.
* Fix for `#171`_: Allow users to specify their own ``SECRET_KEY`` value.
* Moved the dotenv loading to the top of settings.py
* Fix for `#112`_: Added checks for binaries required for document
  consumption.

0.3.4
=====

* Removal of django-suit due to a licensing conflict I bumped into in 0.3.3.
  Note that you *can* use Django Suit with Paperless, but only in a
  non-profit situation as their free license prohibits for-profit use.  As a
  result, I can't bundle Suit with Paperless without conflicting with the
  GPL.  Further development will be done against the stock Django admin.
* I shrunk the thumbnails a little 'cause they were too big for me, even on
  my high-DPI monitor.
* BasicAuth support for document and thumbnail downloads, as well as the Push
  API thanks to @thomasbrueggemann.  See `#179`_.

0.3.3
=====

* Thumbnails in the UI and a Django-suit -based face-lift courtesy of @ekw!
* Timezone, items per page, and default language are now all configurable,
  also thanks to @ekw.

0.3.2
=====

* Fix for `#172`_: defaulting ALLOWED_HOSTS to ``["*"]`` and allowing the
  user to set her own value via ``PAPERLESS_ALLOWED_HOSTS`` should the need
  arise.

0.3.1
=====

* Added a default value for ``CONVERT_BINARY``

0.3.0
=====

* Updated to using django-filter 1.x
* Added some system checks so new users aren't confused by misconfigurations.
* Consumer loop time is now configurable for systems with slow writes.  Just
  set ``PAPERLESS_CONSUMER_LOOP_TIME`` to a number of seconds.  The default
  is 10.
* As per `#44`_, we've removed support for ``PAPERLESS_CONVERT``,
  ``PAPERLESS_CONSUME``, and ``PAPERLESS_SECRET``.  Please use
  ``PAPERLESS_CONVERT_BINARY``, ``PAPERLESS_CONSUMPTION_DIR``, and
  ``PAPERLESS_SHARED_SECRET`` respectively instead.

0.2.0
=====

* `#150`_: The media root is now a variable you can set in
  ``paperless.conf``.
* `#148`_: The database location (sqlite) is now a variable you can set in
  ``paperless.conf``.
* `#146`_: Fixed a bug that allowed unauthorised access to the ``/fetch``
  URL.
* `#131`_: Document files are now automatically removed from disk when
  they're deleted in Paperless.
* `#121`_: Fixed a bug where Paperless wasn't setting document creation time
  based on the file naming scheme.
* `#81`_: Added a hook to run an arbitrary script after every document is
  consumed.
* `#98`_: Added optional environment variables for ImageMagick so that it
  doesn't explode when handling Very Large Documents or when it's just
  running on a low-memory system.  Thanks to `Florian Harr`_ for his help on
  this one.
* `#89`_ Ported the auto-tagging code to correspondents as well.  Thanks to
  `Justin Snyman`_ for the pointers in the issue queue.
* Added support for guessing the date from the file name along with the
  correspondent, title, and tags.  Thanks to `Tikitu de Jager`_ for his pull
  request that I took forever to merge and to `Pit`_ for his efforts on the
  regex front.
* `#94`_: Restored support for changing the created date in the UI.  Thanks
  to `Martin Honermeyer`_ and `Tim White`_ for working with me on this.

0.1.1
=====

* Potentially **Breaking Change**: All references to "sender" in the code
  have been renamed to "correspondent" to better reflect the nature of the
  property (one could quite reasonably scan a document before sending it to
  someone.)
* `#67`_: Rewrote the document exporter and added a new importer that allows
  for full metadata retention without depending on the file name and
  modification time.  A big thanks to `Tikitu de Jager`_, `Pit`_,
  `Florian Jung`_, and `Christopher Luu`_ for their code snippets and
  contributing conversation that lead to this change.
* `#20`_: Added *unpaper* support to help in cleaning up the scanned image
  before it's OCR'd.  Thanks to `Pit`_ for this one.
* `#71`_ Added (encrypted) thumbnails in anticipation of a proper UI.
* `#68`_: Added support for using a proper config file at
  ``/etc/paperless.conf`` and modified the systemd unit files to use it.
* Refactored the Vagrant installation process to use environment variables
  rather than asking the user to modify ``settings.py``.
* `#44`_: Harmonise environment variable names with constant names.
* `#60`_: Setup logging to actually use the Python native logging framework.
* `#53`_: Fixed an annoying bug that caused ``.jpeg`` and ``.JPG`` images
  to be imported but made unavailable.

0.1.0
=====

* Docker support!  Big thanks to `Wayne Werner`_, `Brian Conn`_, and
  `Tikitu de Jager`_ for this one, and especially to `Pit`_
  who spearheadded this effort.
* A simple REST API is in place, but it should be considered unstable.
* Cleaned up the consumer to use temporary directories instead of a single
  scratch space.  (Thanks `Pit`_)
* Improved the efficiency of the consumer by parsing pages more intelligently
  and introducing a threaded OCR process (thanks again `Pit`_).
* `#45`_: Cleaned up the logic for tag matching.  Reported by `darkmatter`_.
* `#47`_: Auto-rotate landscape documents.  Reported by `Paul`_ and fixed by
  `Pit`_.
* `#48`_: Matching algorithms should do so on a word boundary (`darkmatter`_)
* `#54`_: Documented the re-tagger (`zedster`_)
* `#57`_: Make sure file is preserved on import failure (`darkmatter`_)
* Added tox with pep8 checking

0.0.6
=====

* Added support for parallel OCR (significant work from `Pit`_)
* Sped up the language detection (significant work from `Pit`_)
* Added simple logging

0.0.5
=====

* Added support for image files as documents (png, jpg, gif, tiff)
* Added a crude means of HTTP POST for document imports
* Added IMAP mail support
* Added a re-tagging utility
* Documentation for the above as well as data migration

0.0.4
=====

* Added automated tagging basted on keyword matching
* Cleaned up the document listing page
* Removed ``User`` and ``Group`` from the admin
* Added ``pytz`` to the list of requirements

0.0.3
=====

* Added basic tagging

0.0.2
=====

* Added language detection
* Added datestamps to ``document_exporter``.
* Changed ``settings.TESSERACT_LANGUAGE`` to ``settings.OCR_LANGUAGE``.

0.0.1
=====

* Initial release

.. _Alexander Menk: https://github.com/amenk
.. _puuu: https://github.com/puuu
.. _WhiteHatTux: https://github.com/WhiteHatTux
.. _Chris Nagy: https://github.com/what-name
.. _sbrl: https://github.com/sbrl
.. _slorenz: https://github.com/sisao
.. _Jo Vandeginste: https://github.com/jovandeginste
.. _zjean: https://github.com/zjean
.. _rYR79435: https://github.com/rYR79435
.. _Michael Shamoon: https://github.com/shamoon
.. _jayme-github: http://github.com/jayme-github
.. _Brian Conn: https://github.com/TheConnMan
.. _Christopher Luu: https://github.com/nuudles
.. _Florian Jung: https://github.com/the01
.. _Tikitu de Jager: https://github.com/tikitu
.. _Paul: https://github.com/polo2ro
.. _Pit: https://github.com/pitkley
.. _Wayne Werner: https://github.com/waynew
.. _darkmatter: https://github.com/darkmatter
.. _zedster: https://github.com/zedster
.. _Martin Honermeyer: https://github.com/djmaze
.. _Tim White: https://github.com/timwhite
.. _Florian Harr: https://github.com/evils
.. _Justin Snyman: https://github.com/stringlytyped
.. _Thomas Brueggemann: https://github.com/thomasbrueggemann
.. _Jake Gysland: https://github.com/jgysland
.. _Strubbl: https://github.com/strubbl
.. _CkuT: https://github.com/CkuT
.. _David Martin: https://github.com/ddddavidmartin
.. _Paperless Desktop: https://github.com/thomasbrueggemann/paperless-desktop
.. _Joshua Gilman: https://github.com/jmgilman
.. _ayounggun: https://github.com/ayounggun
.. _Kusti Skytén: https://github.com/kskyten
.. _maphy-psd: https://github.com/maphy-psd
.. _ishirav: https://github.com/ishirav
.. _Stefan Hagen: https://github.com/xkpd3
.. _dev-rke: https://github.com/dev-rke
.. _Lukas Winkler: https://github.com/Findus23
.. _chris-aeviator: https://github.com/chris-aeviator
.. _Dan Panzarella: https://github.com/pzl
.. _addadi: https://github.com/addadi
.. _BastianPoe: https://github.com/BastianPoe
.. _matthewmoto: https://github.com/matthewmoto
.. _Isaac: https://github.com/isaacsando
.. _Georgi Todorov: https://github.com/TeraHz
.. _Jeffrey Portman: https://github.com/ChromoX
.. _Simon Taddiken: https://github.com/skuzzle
.. _Quentin Dawans: https://github.com/ovv
.. _Martin Arendtsen: https://github.com/Arendtsen
.. _erikarvstedt: https://github.com/erikarvstedt
.. _Kyle Lucy: https://github.com/kmlucy
.. _thinkjk: https://github.com/thinkjk
.. _mcronce: https://github.com/mcronce
.. _Enno Lohmeier: https://github.com/elohmeier
.. _Mark McFate: https://github.com/SummittDweller
.. _dadosch: https://github.com/dadosch
.. _Wolfgang Mader: https://github.com/wmader
.. _Tim Brooks: https://github.com/brookst
.. _Stéphane Brunner: https://github.com/sbrunner
.. _Kilian Koeltzsch: https://github.com/kiliankoe
.. _Lukasz Soluch: https://github.com/LukaszSolo
.. _Joshua Taillon: https://github.com/jat255
.. _dubit0: https://github.com/dubit0
.. _ahyear: https://github.com/ahyear
.. _jonaswinkler: https://github.com/jonaswinkler
.. _thepill: https://github.com/thepill
.. _Andrew Peng: https://github.com/pengc99
.. _euri10: https://github.com/euri10
.. _Ulli: https://github.com/Ulli2k
.. _tsia: https://github.com/tsia
.. _Sblop: https://github.com/Sblop
.. _Colin Frei: https://github.com/colinfrei
.. _khrise: https://github.com/khrise
.. _syntonym: https://github.com/syntonym
.. _JOKer: https://github.com/MasterofJOKers
.. _Brian Cribbs: https://github.com/cribbstechnolog
.. _Brendan M. Sleight: https://github.com/bmsleight
.. _Daniel Albers: https://github.com/AlD

.. _#20: https://github.com/the-paperless-project/paperless/issues/20
.. _#44: https://github.com/the-paperless-project/paperless/issues/44
.. _#45: https://github.com/the-paperless-project/paperless/issues/45
.. _#47: https://github.com/the-paperless-project/paperless/issues/47
.. _#48: https://github.com/the-paperless-project/paperless/issues/48
.. _#53: https://github.com/the-paperless-project/paperless/issues/53
.. _#54: https://github.com/the-paperless-project/paperless/issues/54
.. _#57: https://github.com/the-paperless-project/paperless/issues/57
.. _#60: https://github.com/the-paperless-project/paperless/issues/60
.. _#67: https://github.com/the-paperless-project/paperless/issues/67
.. _#68: https://github.com/the-paperless-project/paperless/issues/68
.. _#71: https://github.com/the-paperless-project/paperless/issues/71
.. _#81: https://github.com/the-paperless-project/paperless/issues/81
.. _#89: https://github.com/the-paperless-project/paperless/issues/89
.. _#94: https://github.com/the-paperless-project/paperless/issues/94
.. _#98: https://github.com/the-paperless-project/paperless/issues/98
.. _#112: https://github.com/the-paperless-project/paperless/issues/112
.. _#121: https://github.com/the-paperless-project/paperless/issues/121
.. _#131: https://github.com/the-paperless-project/paperless/issues/131
.. _#146: https://github.com/the-paperless-project/paperless/issues/146
.. _#148: https://github.com/the-paperless-project/paperless/pull/148
.. _#150: https://github.com/the-paperless-project/paperless/pull/150
.. _#158: https://github.com/the-paperless-project/paperless/issues/158
.. _#171: https://github.com/the-paperless-project/paperless/issues/171
.. _#172: https://github.com/the-paperless-project/paperless/issues/172
.. _#179: https://github.com/the-paperless-project/paperless/pull/179
.. _#199: https://github.com/the-paperless-project/paperless/issues/199
.. _#200: https://github.com/the-paperless-project/paperless/issues/200
.. _#206: https://github.com/the-paperless-project/paperless/issues/206
.. _#212: https://github.com/the-paperless-project/paperless/pull/212
.. _#220: https://github.com/the-paperless-project/paperless/pull/220
.. _#224: https://github.com/the-paperless-project/paperless/pull/224
.. _#226: https://github.com/the-paperless-project/paperless/pull/226
.. _#227: https://github.com/the-paperless-project/paperless/pull/227
.. _#228: https://github.com/the-paperless-project/paperless/pull/228
.. _#229: https://github.com/the-paperless-project/paperless/pull/229
.. _#230: https://github.com/the-paperless-project/paperless/pull/230
.. _#232: https://github.com/the-paperless-project/paperless/issues/232
.. _#235: https://github.com/the-paperless-project/paperless/issues/235
.. _#236: https://github.com/the-paperless-project/paperless/issues/236
.. _#255: https://github.com/the-paperless-project/paperless/pull/255
.. _#268: https://github.com/the-paperless-project/paperless/pull/268
.. _#277: https://github.com/the-paperless-project/paperless/pull/277
.. _#272: https://github.com/the-paperless-project/paperless/issues/272
.. _#248: https://github.com/the-paperless-project/paperless/issues/248
.. _#278: https://github.com/the-paperless-project/paperless/issues/248
.. _#283: https://github.com/the-paperless-project/paperless/issues/283
.. _#256: https://github.com/the-paperless-project/paperless/pull/256
.. _#285: https://github.com/the-paperless-project/paperless/pull/285
.. _#291: https://github.com/the-paperless-project/paperless/pull/291
.. _#295: https://github.com/the-paperless-project/paperless/pull/295
.. _#299: https://github.com/the-paperless-project/paperless/issues/299
.. _#300: https://github.com/the-paperless-project/paperless/pull/300
.. _#301: https://github.com/the-paperless-project/paperless/issues/301
.. _#303: https://github.com/the-paperless-project/paperless/issues/303
.. _#305: https://github.com/the-paperless-project/paperless/issues/305
.. _#306: https://github.com/the-paperless-project/paperless/issues/306
.. _#308: https://github.com/the-paperless-project/paperless/issues/308
.. _#311: https://github.com/the-paperless-project/paperless/pull/311
.. _#312: https://github.com/the-paperless-project/paperless/pull/312
.. _#313: https://github.com/the-paperless-project/paperless/pull/313
.. _#322: https://github.com/the-paperless-project/paperless/pull/322
.. _#328: https://github.com/the-paperless-project/paperless/pull/328
.. _#253: https://github.com/the-paperless-project/paperless/issues/253
.. _#262: https://github.com/the-paperless-project/paperless/issues/262
.. _#323: https://github.com/the-paperless-project/paperless/issues/323
.. _#344: https://github.com/the-paperless-project/paperless/pull/344
.. _#351: https://github.com/the-paperless-project/paperless/pull/351
.. _#352: https://github.com/the-paperless-project/paperless/pull/352
.. _#354: https://github.com/the-paperless-project/paperless/issues/354
.. _#371: https://github.com/the-paperless-project/paperless/issues/371
.. _#374: https://github.com/the-paperless-project/paperless/pull/374
.. _#375: https://github.com/the-paperless-project/paperless/pull/375
.. _#376: https://github.com/the-paperless-project/paperless/pull/376
.. _#383: https://github.com/the-paperless-project/paperless/pull/383
.. _#384: https://github.com/the-paperless-project/paperless/issues/384
.. _#386: https://github.com/the-paperless-project/paperless/issues/386
.. _#387: https://github.com/the-paperless-project/paperless/pull/387
.. _#391: https://github.com/the-paperless-project/paperless/pull/391
.. _#390: https://github.com/the-paperless-project/paperless/pull/390
.. _#392: https://github.com/the-paperless-project/paperless/issues/392
.. _#393: https://github.com/the-paperless-project/paperless/issues/393
.. _#395: https://github.com/the-paperless-project/paperless/pull/395
.. _#394: https://github.com/the-paperless-project/paperless/issues/394
.. _#396: https://github.com/the-paperless-project/paperless/pull/396
.. _#399: https://github.com/the-paperless-project/paperless/pull/399
.. _#400: https://github.com/the-paperless-project/paperless/pull/400
.. _#401: https://github.com/the-paperless-project/paperless/pull/401
.. _#405: https://github.com/the-paperless-project/paperless/pull/405
.. _#406: https://github.com/the-paperless-project/paperless/issues/406
.. _#412: https://github.com/the-paperless-project/paperless/issues/412
.. _#413: https://github.com/the-paperless-project/paperless/pull/413
.. _#414: https://github.com/the-paperless-project/paperless/issues/414
.. _#423: https://github.com/the-paperless-project/paperless/issues/423
.. _#433: https://github.com/the-paperless-project/paperless/issues/433
.. _#440: https://github.com/the-paperless-project/paperless/pull/440
.. _#441: https://github.com/the-paperless-project/paperless/pull/441
.. _#442: https://github.com/the-paperless-project/paperless/pull/442
.. _#466: https://github.com/the-paperless-project/paperless/pull/466
.. _#471: https://github.com/the-paperless-project/paperless/pull/471
.. _#475: https://github.com/the-paperless-project/paperless/pull/475
.. _#481: https://github.com/the-paperless-project/paperless/pull/481
.. _#483: https://github.com/the-paperless-project/paperless/pull/483
.. _#484: https://github.com/the-paperless-project/paperless/pull/484
.. _#488: https://github.com/the-paperless-project/paperless/pull/488
.. _#489: https://github.com/the-paperless-project/paperless/pull/489
.. _#492: https://github.com/the-paperless-project/paperless/pull/492

.. _a new home on Docker Hub: https://hub.docker.com/r/danielquinn/paperless/
.. _optipng: http://optipng.sourceforge.net/
.. _DjangoQL: https://github.com/ivelum/djangoql
