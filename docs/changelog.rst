Changelog
#########

* 0.8.0
  * Paperless can now run in a subdirectory on a host (``/paperless``), rather
    than always running in the root (``/``) thanks to `maphy-psd`_'s work on
    `#255`_.

* 0.7.0
  * **Potentially breaking change**: As per `#235`_, Paperless will no longer
    automatically delete documents attached to correspondents when those
    correspondents are themselves deleted.  This was Django's default
    behaviour, but didn't make much sense in Paperless' case.  Thanks to
    `Thomas Brueggemann`_ and `David Martin`_ for their input on this one.
  * Fix for `#232`_ wherein Paperless wasn't recognising ``.tif`` files
    properly.  Thanks to `ayounggun`_ for reporting this one and to
    `Kusti Skytén`_ for posting the correct solution in the Github issue.

* 0.6.0
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
* 0.5.0
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

* 0.4.1
  * Fix for `#206`_ wherein the pluggable parser didn't recognise files with
    all-caps suffixes like ``.PDF``

* 0.4.0
  * Introducing reminders.  See `#199`_ for more information, but the short
    explanation is that you can now attach simple notes & times to documents
    which are made available via the API.  Currently, the default API
    (basically just the Django admin) doesn't really make use of this, but
    `Thomas Brueggemann`_ over at `Paperless Desktop`_ has said that he would
    like to make use of this feature in his project.

* 0.3.6
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

* 0.3.5
  * A serious facelift for the documents listing page wherein we drop the
    tabular layout in favour of a tiled interface.
  * Users can now configure the number of items per page.
  * Fix for `#171`_: Allow users to specify their own ``SECRET_KEY`` value.
  * Moved the dotenv loading to the top of settings.py
  * Fix for `#112`_: Added checks for binaries required for document
    consumption.

* 0.3.4
  * Removal of django-suit due to a licensing conflict I bumped into in 0.3.3.
    Note that you *can* use Django Suit with Paperless, but only in a
    non-profit situation as their free license prohibits for-profit use.  As a
    result, I can't bundle Suit with Paperless without conflicting with the
    GPL.  Further development will be done against the stock Django admin.
  * I shrunk the thumbnails a little 'cause they were too big for me, even on
    my high-DPI monitor.
  * BasicAuth support for document and thumbnail downloads, as well as the Push
    API thanks to @thomasbrueggemann.  See `#179`_.

* 0.3.3
  * Thumbnails in the UI and a Django-suit -based face-lift courtesy of @ekw!
  * Timezone, items per page, and default language are now all configurable,
    also thanks to @ekw.

* 0.3.2
  * Fix for `#172`_: defaulting ALLOWED_HOSTS to ``["*"]`` and allowing the
    user to set her own value via ``PAPERLESS_ALLOWED_HOSTS`` should the need
    arise.

* 0.3.1
  * Added a default value for ``CONVERT_BINARY``

* 0.3.0
  * Updated to using django-filter 1.x
  * Added some system checks so new users aren't confused by misconfigurations.
  * Consumer loop time is now configurable for systems with slow writes.  Just
    set ``PAPERLESS_CONSUMER_LOOP_TIME`` to a number of seconds.  The default
    is 10.
  * As per `#44`_, we've removed support for ``PAPERLESS_CONVERT``,
    ``PAPERLESS_CONSUME``, and ``PAPERLESS_SECRET``.  Please use
    ``PAPERLESS_CONVERT_BINARY``, ``PAPERLESS_CONSUMPTION_DIR``, and
    ``PAPERLESS_SHARED_SECRET`` respectively instead.

* 0.2.0

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

* 0.1.1

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

* 0.1.0

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

* 0.0.6

  * Added support for parallel OCR (significant work from `Pit`_)
  * Sped up the language detection (significant work from `Pit`_)
  * Added simple logging

* 0.0.5

  * Added support for image files as documents (png, jpg, gif, tiff)
  * Added a crude means of HTTP POST for document imports
  * Added IMAP mail support
  * Added a re-tagging utility
  * Documentation for the above as well as data migration

* 0.0.4

  * Added automated tagging basted on keyword matching
  * Cleaned up the document listing page
  * Removed ``User`` and ``Group`` from the admin
  * Added ``pytz`` to the list of requirements

* 0.0.3

  * Added basic tagging

* 0.0.2

  * Added language detection
  * Added datestamps to ``document_exporter``.
  * Changed ``settings.TESSERACT_LANGUAGE`` to ``settings.OCR_LANGUAGE``.

* 0.0.1

  * Initial release

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

.. _#20: https://github.com/danielquinn/paperless/issues/20
.. _#44: https://github.com/danielquinn/paperless/issues/44
.. _#45: https://github.com/danielquinn/paperless/issues/45
.. _#47: https://github.com/danielquinn/paperless/issues/47
.. _#48: https://github.com/danielquinn/paperless/issues/48
.. _#53: https://github.com/danielquinn/paperless/issues/53
.. _#54: https://github.com/danielquinn/paperless/issues/54
.. _#57: https://github.com/danielquinn/paperless/issues/57
.. _#60: https://github.com/danielquinn/paperless/issues/60
.. _#67: https://github.com/danielquinn/paperless/issues/67
.. _#68: https://github.com/danielquinn/paperless/issues/68
.. _#71: https://github.com/danielquinn/paperless/issues/71
.. _#81: https://github.com/danielquinn/paperless/issues/81
.. _#89: https://github.com/danielquinn/paperless/issues/89
.. _#94: https://github.com/danielquinn/paperless/issues/94
.. _#98: https://github.com/danielquinn/paperless/issues/98
.. _#112: https://github.com/danielquinn/paperless/issues/112
.. _#121: https://github.com/danielquinn/paperless/issues/121
.. _#131: https://github.com/danielquinn/paperless/issues/131
.. _#146: https://github.com/danielquinn/paperless/issues/146
.. _#148: https://github.com/danielquinn/paperless/pull/148
.. _#150: https://github.com/danielquinn/paperless/pull/150
.. _#171: https://github.com/danielquinn/paperless/issues/171
.. _#172: https://github.com/danielquinn/paperless/issues/172
.. _#179: https://github.com/danielquinn/paperless/pull/179
.. _#199: https://github.com/danielquinn/paperless/issues/199
.. _#200: https://github.com/danielquinn/paperless/issues/200
.. _#206: https://github.com/danielquinn/paperless/issues/206
.. _#212: https://github.com/danielquinn/paperless/pull/212
.. _#220: https://github.com/danielquinn/paperless/pull/220
.. _#224: https://github.com/danielquinn/paperless/pull/224
.. _#226: https://github.com/danielquinn/paperless/pull/226
.. _#227: https://github.com/danielquinn/paperless/pull/227
.. _#228: https://github.com/danielquinn/paperless/pull/228
.. _#229: https://github.com/danielquinn/paperless/pull/229
.. _#230: https://github.com/danielquinn/paperless/pull/230
.. _#232: https://github.com/danielquinn/paperless/issues/232
.. _#235: https://github.com/danielquinn/paperless/issues/235
.. _#236: https://github.com/danielquinn/paperless/issues/236
.. _#255: https://github.com/danielquinn/paperless/pull/255
