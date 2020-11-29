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
    report.
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

.. warning::

    This section is not updated to paperless-ng yet.

For the most part, Paperless is monolithic, so extending it is often best
managed by way of modifying the code directly and issuing a pull request on
`GitHub`_.  However, over time the project has been evolving to be a little
more "pluggable" so that users can write their own stuff that talks to it.

.. _GitHub: https://github.com/the-paperless-project/paperless


.. _extending-parsers:

Parsers
-------

You can leverage Paperless' consumption model to have it consume files *other*
than ones handled by default like ``.pdf``, ``.jpg``, and ``.tiff``.  To do so,
you simply follow Django's convention of creating a new app, with a few key
requirements.


.. _extending-parsers-parserspy:

parsers.py
..........

In this file, you create a class that extends
``documents.parsers.DocumentParser`` and go about implementing the three
required methods:

* ``get_thumbnail()``: Returns the path to a file we can use as a thumbnail for
  this document.
* ``get_text()``: Returns the text from the document and only the text.
* ``get_date()``: If possible, this returns the date of the document, otherwise
  it should return ``None``.


.. _extending-parsers-signalspy:

signals.py
..........

At consumption time, Paperless emits a ``document_consumer_declaration``
signal which your module has to react to in order to let the consumer know
whether or not it's capable of handling a particular file.  Think of it like
this:

1. Consumer finds a file in the consumption directory.
2. It asks all the available parsers: *"Hey, can you handle this file?"*
3. Each parser responds with either ``None`` meaning they can't handle the
   file, or a dictionary in the following format:

.. code:: python

    {
        "parser": <the class name>,
        "weight": <an integer>
    }

The consumer compares the ``weight`` values from all respondents and uses the
class with the highest value to consume the document.  The default parser,
``RasterisedDocumentParser`` has a weight of ``0``.


.. _extending-parsers-appspy:

apps.py
.......

This is a standard Django file, but you'll need to add some code to it to
connect your parser to the ``document_consumer_declaration`` signal.


.. _extending-parsers-finally:

Finally
.......

The last step is to update ``settings.py`` to include your new module.
Eventually, this will be dynamic, but at the moment, you have to edit the
``INSTALLED_APPS`` section manually.  Simply add the path to your AppConfig to
the list like this:

.. code:: python

    INSTALLED_APPS = [
        ...
        "my_module.apps.MyModuleConfig",
        ...
    ]

Order doesn't matter, but generally it's a good idea to place your module lower
in the list so that you don't end up accidentally overriding project defaults
somewhere.


.. _extending-parsers-example:

An Example
..........

The core Paperless functionality is based on this design, so if you want to see
what a parser module should look like, have a look at `parsers.py`_,
`signals.py`_, and `apps.py`_ in the `paperless_tesseract`_ module.

.. _parsers.py: https://github.com/the-paperless-project/paperless/blob/master/src/paperless_tesseract/parsers.py
.. _signals.py: https://github.com/the-paperless-project/paperless/blob/master/src/paperless_tesseract/signals.py
.. _apps.py: https://github.com/the-paperless-project/paperless/blob/master/src/paperless_tesseract/apps.py
.. _paperless_tesseract: https://github.com/the-paperless-project/paperless/blob/master/src/paperless_tesseract/
