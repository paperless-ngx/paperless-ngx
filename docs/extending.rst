.. _extending:

Paperless development
#####################

This section describes the steps you need to take to start development on paperless-ng.

1.  Check out the source from github. The repository is organized in the following way:

    *   ``master`` always represents the latest release and will only see changes
        when a new release is made.
    *   ``dev`` contains the code that will be in the next release.
    *   ``feature-X`` contain bigger changes that will be in some release, but not
        necessarily the next one.
    
    Apart from that, the folder structure is as follows:

    *   ``docs/`` - Documentation.
    *   ``src-ui/`` - Code of the front end.
    *   ``src/`` - Code of the back end.
    *   ``scripts/`` - Various scripts that help with different parts of development.
    *   ``docker/`` - Files required to build the docker image.

2.  Install some dependencies.

    *   Python 3.6.
    *   All dependencies listed in the :ref:`Bare metal route <setup-bare_metal>`
    *   redis. You can either install redis or use the included scritps/start-redis.sh
        to use docker to fire up a redis instance.

Back end development
====================

The backend is a django application. I use PyCharm for development, but you can use whatever
you want.

Install the python dependencies by performing ``pipenv install --dev`` in the src/ directory.
This will also create a virtual environment, which you can enter with ``pipenv shell`` or
execute one-shot commands in with ``pipenv run``.

In ``src/paperless.conf``, enable debug mode.

Configure the IDE to use the src/ folder as the base source folder. Configure the following
launch configurations in your IDE:

*   python3 manage.py runserver
*   python3 manage.py qcluster
*   python3 manage.py consumer

Depending on which part of paperless you're developing for, you need to have some or all of
them running.

Testing and code style:

*   Run ``pytest`` in the src/ directory to execute all tests. This also generates a HTML coverage
    report. When runnings test, paperless.conf is loaded as well. However: the tests rely on the default
    configuration. This is not ideal. But for now, make sure no settings except for DEBUG are overridden when testing.
*   Run ``pycodestyle`` to test your code for issues with the configured code style settings.

    .. note::

        The line length rule E501 is generally useful for getting multiple source files
        next to each other on the screen. However, in some cases, its just not possible
        to make some lines fit, especially complicated IF cases. Append ``  # NOQA: E501``
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

    $ ng build --prod --output-path ../src/documents/static/frontend/

This will build the front end and put it in a location from which the Django server will serve
it as static content. This way, you can verify that authentication is working.

Making a release
================

Execute the ``make-release.sh <ver>`` script.

This will test and assemble everything and also build and tag a docker image.


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
