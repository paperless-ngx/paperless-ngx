Changelog
#########

2.6.1
=====

* We now have a logo, complete with a favicon :-)
* Removed some problematic tests.
* Fix the docker-compose example config to include a shared consume volume so
  that using the push API will work for users of the Docker install.  Thanks to
  `Colin Frei`_ for fixing this in `#466`_.
* `khrise`_ submitted a pull request to include the ``added`` property to the
  REST API `#471`.


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
------------------

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
.. _#158: https://github.com/danielquinn/paperless/issues/158
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
.. _#268: https://github.com/danielquinn/paperless/pull/268
.. _#277: https://github.com/danielquinn/paperless/pull/277
.. _#272: https://github.com/danielquinn/paperless/issues/272
.. _#248: https://github.com/danielquinn/paperless/issues/248
.. _#278: https://github.com/danielquinn/paperless/issues/248
.. _#283: https://github.com/danielquinn/paperless/issues/283
.. _#256: https://github.com/danielquinn/paperless/pull/256
.. _#285: https://github.com/danielquinn/paperless/pull/285
.. _#291: https://github.com/danielquinn/paperless/pull/291
.. _#295: https://github.com/danielquinn/paperless/pull/295
.. _#299: https://github.com/danielquinn/paperless/issues/299
.. _#300: https://github.com/danielquinn/paperless/pull/300
.. _#301: https://github.com/danielquinn/paperless/issues/301
.. _#303: https://github.com/danielquinn/paperless/issues/303
.. _#305: https://github.com/danielquinn/paperless/issues/305
.. _#306: https://github.com/danielquinn/paperless/issues/306
.. _#308: https://github.com/danielquinn/paperless/issues/308
.. _#311: https://github.com/danielquinn/paperless/pull/311
.. _#312: https://github.com/danielquinn/paperless/pull/312
.. _#313: https://github.com/danielquinn/paperless/pull/313
.. _#322: https://github.com/danielquinn/paperless/pull/322
.. _#328: https://github.com/danielquinn/paperless/pull/328
.. _#253: https://github.com/danielquinn/paperless/issues/253
.. _#262: https://github.com/danielquinn/paperless/issues/262
.. _#323: https://github.com/danielquinn/paperless/issues/323
.. _#344: https://github.com/danielquinn/paperless/pull/344
.. _#351: https://github.com/danielquinn/paperless/pull/351
.. _#352: https://github.com/danielquinn/paperless/pull/352
.. _#354: https://github.com/danielquinn/paperless/issues/354
.. _#371: https://github.com/danielquinn/paperless/issues/371
.. _#374: https://github.com/danielquinn/paperless/pull/374
.. _#375: https://github.com/danielquinn/paperless/pull/375
.. _#376: https://github.com/danielquinn/paperless/pull/376
.. _#383: https://github.com/danielquinn/paperless/pull/383
.. _#384: https://github.com/danielquinn/paperless/issues/384
.. _#386: https://github.com/danielquinn/paperless/issues/386
.. _#387: https://github.com/danielquinn/paperless/pull/387
.. _#391: https://github.com/danielquinn/paperless/pull/391
.. _#390: https://github.com/danielquinn/paperless/pull/390
.. _#392: https://github.com/danielquinn/paperless/issues/392
.. _#393: https://github.com/danielquinn/paperless/issues/393
.. _#395: https://github.com/danielquinn/paperless/pull/395
.. _#394: https://github.com/danielquinn/paperless/issues/394
.. _#396: https://github.com/danielquinn/paperless/pull/396
.. _#399: https://github.com/danielquinn/paperless/pull/399
.. _#400: https://github.com/danielquinn/paperless/pull/400
.. _#401: https://github.com/danielquinn/paperless/pull/401
.. _#405: https://github.com/danielquinn/paperless/pull/405
.. _#406: https://github.com/danielquinn/paperless/issues/406
.. _#412: https://github.com/danielquinn/paperless/issues/412
.. _#413: https://github.com/danielquinn/paperless/pull/413
.. _#414: https://github.com/danielquinn/paperless/issues/414
.. _#423: https://github.com/danielquinn/paperless/issues/423
.. _#433: https://github.com/danielquinn/paperless/issues/433
.. _#440: https://github.com/danielquinn/paperless/pull/440
.. _#441: https://github.com/danielquinn/paperless/pull/441
.. _#442: https://github.com/danielquinn/paperless/pull/442
.. _#466: https://github.com/danielquinn/paperless/pull/466
.. _#471: https://github.com/danielquinn/paperless/pull/471

.. _pipenv: https://docs.pipenv.org/
.. _a new home on Docker Hub: https://hub.docker.com/r/danielquinn/paperless/
.. _optipng: http://optipng.sourceforge.net/
