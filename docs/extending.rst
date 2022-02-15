.. _extending:

Paperless development
#####################

This section describes the steps you need to take to start development on paperless-ng.

Check out the source from github. The repository is organized in the following way:

*   ``master`` always represents the latest release and will only see changes
    when a new release is made.
*   ``dev`` contains the code that will be in the next release.
*   ``feature-X`` contain bigger changes that will be in some release, but not
    necessarily the next one.

When making functional changes to paperless, *always* make your changes on the ``dev`` branch.

Apart from that, the folder structure is as follows:

*   ``docs/`` - Documentation.
*   ``src-ui/`` - Code of the front end.
*   ``src/`` - Code of the back end.
*   ``scripts/`` - Various scripts that help with different parts of development.
*   ``docker/`` - Files required to build the docker image.

Initial setup and first start
=============================

After you forked and cloned the code from github you need to perform a first-time setup.
To do the setup you need to perform the steps from the following chapters in a certain order:

1.  Install prerequisites + pipenv as mentioned in :ref:`Bare metal route <setup-bare_metal>`
2.  Copy ``paperless.conf.example`` to ``paperless.conf`` and enable debug mode.
3.  Install the Angular CLI interface:

    .. code:: shell-session

        $ npm install -g @angular/cli

4.  Create ``consume`` and ``media`` folders in the cloned root folder.

    .. code:: shell-session

        mkdir -p consume media

5.  You can now either ...

    *  install redis or
    *  use the included scripts/start-services.sh to use docker to fire up a redis instance (and some other services such as tika, gotenberg and a postgresql server) or
    *  spin up a bare redis container

        .. code:: shell-session

            docker run -d -p 6379:6379 -restart unless-stopped redis:latest

6.  Install the python dependencies by performing in the src/ directory.

    .. code:: shell-session

        pipenv install --dev

7.  Generate the static UI so you can perform a login to get session that is required for frontend development (this needs to be done one time only). From root folder:

    .. code:: shell-session

        compile-frontend.sh

8.  Apply migrations and create a superuser for your dev instance:

    .. code:: shell-session

        python3 manage.py migrate
        python3 manage.py createsuperuser

9.  Now spin up the dev backend. Depending on which part of paperless you're developing for, you need to have some or all of them running.

    .. code:: shell-session

        python3 manage.py runserver & python3 manage.py document_consumer & python3 manage.py qcluster

10. Login with the superuser credentials provided in step 8 at ``http://localhost:8000`` to create a session that enables you to use the backend.

Backend development environment is now ready, to start Frontend development go to ``/src-ui`` and run ``ng serve``. From there you can use ``http://localhost:4200`` for a preview.

Back end development
====================

The backend is a django application. I use PyCharm for development, but you can use whatever
you want.

Configure the IDE to use the src/ folder as the base source folder. Configure the following
launch configurations in your IDE:

*   python3 manage.py runserver
*   python3 manage.py qcluster
*   python3 manage.py document_consumer

To start them all:

.. code:: shell-session

    python3 manage.py runserver & python3 manage.py document_consumer & python3 manage.py qcluster

Testing and code style:

*   Run ``pytest`` in the src/ directory to execute all tests. This also generates a HTML coverage
    report. When runnings test, paperless.conf is loaded as well. However: the tests rely on the default
    configuration. This is not ideal. But for now, make sure no settings except for DEBUG are overridden when testing.
*   Run ``pycodestyle`` to test your code for issues with the configured code style settings.

    .. note::

        The line length rule E501 is generally useful for getting multiple source files
        next to each other on the screen. However, in some cases, its just not possible
        to make some lines fit, especially complicated IF cases. Append ``# NOQA: E501``
        to disable this check for certain lines.

Front end development
=====================

The front end is build using angular. I use the ``Code - OSS`` IDE for development.

In order to get started, you need ``npm``. Install the Angular CLI interface with

.. code:: shell-session

    $ npm install -g @angular/cli

and make sure that it's on your path. Next, in the src-ui/ directory, install the
required dependencies of the project.

.. code:: shell-session

    $ npm install

You can launch a development server by running

.. code:: shell-session

    $ ng serve

This will automatically update whenever you save. However, in-place compilation might fail
on syntax errors, in which case you need to restart it.

By default, the development server is available on ``http://localhost:4200/`` and is configured
to access the API at ``http://localhost:8000/api/``, which is the default of the backend.
If you enabled DEBUG on the back end, several security overrides for allowed hosts, CORS and
X-Frame-Options are in place so that the front end behaves exactly as in production. This also
relies on you being logged into the back end. Without a valid session, The front end will simply
not work.

In order to build the front end and serve it as part of django, execute

.. code:: shell-session

    $ ng build --prod

This will build the front end and put it in a location from which the Django server will serve
it as static content. This way, you can verify that authentication is working.


Localization
============

Paperless is available in many different languages. Since paperless consists both of a django
application and an Angular front end, both these parts have to be translated separately.

Front end localization
----------------------

*   The Angular front end does localization according to the `Angular documentation <https://angular.io/guide/i18n>`_.
*   The source language of the project is "en_US".
*   The source strings end up in the file "src-ui/messages.xlf".
*   The translated strings need to be placed in the "src-ui/src/locale/" folder.
*   In order to extract added or changed strings from the source files, call ``ng xi18n --ivy``.

Adding new languages requires adding the translated files in the "src-ui/src/locale/" folder and adjusting a couple files.

1.  Adjust "src-ui/angular.json":

    .. code:: json

        "i18n": {
            "sourceLocale": "en-US",
            "locales": {
                "de": "src/locale/messages.de.xlf",
                "nl-NL": "src/locale/messages.nl_NL.xlf",
                "fr": "src/locale/messages.fr.xlf",
                "en-GB": "src/locale/messages.en_GB.xlf",
                "pt-BR": "src/locale/messages.pt_BR.xlf",
                "language-code": "language-file"
            }
        }

2.  Add the language to the available options in "src-ui/src/app/services/settings.service.ts":

    .. code:: typescript

        getLanguageOptions(): LanguageOption[] {
            return [
                {code: "en-us", name: $localize`English (US)`, englishName: "English (US)", dateInputFormat: "mm/dd/yyyy"},
                {code: "en-gb", name: $localize`English (GB)`, englishName: "English (GB)", dateInputFormat: "dd/mm/yyyy"},
                {code: "de", name: $localize`German`, englishName: "German", dateInputFormat: "dd.mm.yyyy"},
                {code: "nl", name: $localize`Dutch`, englishName: "Dutch", dateInputFormat: "dd-mm-yyyy"},
                {code: "fr", name: $localize`French`, englishName: "French", dateInputFormat: "dd/mm/yyyy"},
                {code: "pt-br", name: $localize`Portuguese (Brazil)`, englishName: "Portuguese (Brazil)", dateInputFormat: "dd/mm/yyyy"}
                // Add your new language here
            ]
        }

    ``dateInputFormat`` is a special string that defines the behavior of the date input fields and absolutely needs to contain "dd", "mm" and "yyyy".

3.  Import and register the Angular data for this locale in "src-ui/src/app/app.module.ts":

    .. code:: typescript

        import localeDe from '@angular/common/locales/de';
        registerLocaleData(localeDe)

Back end localization
---------------------

A majority of the strings that appear in the back end appear only when the admin is used. However,
some of these are still shown on the front end (such as error messages).

*   The django application does localization according to the `django documentation <https://docs.djangoproject.com/en/3.1/topics/i18n/translation/>`_.
*   The source language of the project is "en_US".
*   Localization files end up in the folder "src/locale/".
*   In order to extract strings from the application, call ``python3 manage.py makemessages -l en_US``. This is important after making changes to translatable strings.
*   The message files need to be compiled for them to show up in the application. Call ``python3 manage.py compilemessages`` to do this. The generated files don't get
    committed into git, since these are derived artifacts. The build pipeline takes care of executing this command.

Adding new languages requires adding the translated files in the "src/locale/" folder and adjusting the file "src/paperless/settings.py" to include the new language:

.. code:: python

    LANGUAGES = [
        ("en-us", _("English (US)")),
        ("en-gb", _("English (GB)")),
        ("de", _("German")),
        ("nl-nl", _("Dutch")),
        ("fr", _("French")),
        ("pt-br", _("Portuguese (Brazil)")),
        # Add language here.
    ]


Building the documentation
==========================

The documentation is built using sphinx. I've configured ReadTheDocs to automatically build
the documentation when changes are pushed. If you want to build the documentation locally,
this is how you do it:

1.  Install python dependencies.

    .. code:: shell-session

        $ cd /path/to/paperless
        $ pipenv install --dev

2.  Build the documentation

    .. code:: shell-session

        $ cd /path/to/paperless/docs
        $ pipenv run make clean html

This will build the HTML documentation, and put the resulting files in the ``_build/html``
directory.

Building the Docker image
=========================

Building the docker image from source requires the following two steps:

1.  Build the front end.

    .. code:: shell-session

        ./compile-frontend.sh

2.  Build the docker image.

    .. code:: shell-session

        docker build . -t <your-tag>

Extending Paperless
===================

Paperless does not have any fancy plugin systems and will probably never have. However,
some parts of the application have been designed to allow easy integration of additional
features without any modification to the base code.

Making custom parsers
---------------------

Paperless uses parsers to add documents to paperless. A parser is responsible for:

*   Retrieve the content from the original
*   Create a thumbnail
*   Optional: Retrieve a created date from the original
*   Optional: Create an archived document from the original

Custom parsers can be added to paperless to support more file types. In order to do that,
you need to write the parser itself and announce its existence to paperless.

The parser itself must extend ``documents.parsers.DocumentParser`` and must implement the
methods ``parse`` and ``get_thumbnail``. You can provide your own implementation to
``get_date`` if you don't want to rely on paperless' default date guessing mechanisms.

.. code:: python

    class MyCustomParser(DocumentParser):

        def parse(self, document_path, mime_type):
            # This method does not return anything. Rather, you should assign
            # whatever you got from the document to the following fields:

            # The content of the document.
            self.text = "content"

            # Optional: path to a PDF document that you created from the original.
            self.archive_path = os.path.join(self.tempdir, "archived.pdf")

            # Optional: "created" date of the document.
            self.date = get_created_from_metadata(document_path)

        def get_thumbnail(self, document_path, mime_type):
            # This should return the path to a thumbnail you created for this
            # document.
            return os.path.join(self.tempdir, "thumb.png")

If you encounter any issues during parsing, raise a ``documents.parsers.ParseError``.

The ``self.tempdir`` directory is a temporary directory that is guaranteed to be empty
and removed after consumption finished. You can use that directory to store any
intermediate files and also use it to store the thumbnail / archived document.

After that, you need to announce your parser to paperless. You need to connect a
handler to the ``document_consumer_declaration`` signal. Have a look in the file
``src/paperless_tesseract/apps.py`` on how that's done. The handler is a method
that returns information about your parser:

.. code:: python

    def myparser_consumer_declaration(sender, **kwargs):
        return {
            "parser": MyCustomParser,
            "weight": 0,
            "mime_types": {
                "application/pdf": ".pdf",
                "image/jpeg": ".jpg",
            }
        }

*   ``parser`` is a reference to a class that extends ``DocumentParser``.

*   ``weight`` is used whenever two or more parsers are able to parse a file: The parser with
    the higher weight wins. This can be used to override the parsers provided by
    paperless.

*   ``mime_types`` is a dictionary. The keys are the mime types your parser supports and the value
    is the default file extension that paperless should use when storing files and serving them for
    download. We could guess that from the file extensions, but some mime types have many extensions
    associated with them and the python methods responsible for guessing the extension do not always
    return the same value.
