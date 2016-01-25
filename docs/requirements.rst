.. _requirements:

Requirements
============

You need a Linux machine or Unix-like setup (theoretically an Apple machine
should work) that has the following software installed on it:

* `Python3`_ (with development libraries, pip and virtualenv)
* `GNU Privacy Guard`_
* `Tesseract`_
* `Imagemagick`_

.. _Python3: https://python.org/
.. _GNU Privacy Guard: https://gnupg.org
.. _Tesseract: https://github.com/tesseract-ocr
.. _Imagemagick: http://imagemagick.org/

If you're not working on a virtual environment (like Vagrant or Docker), you
should probably be using a virtualenv, but that's your call.  The reasons why
you might choose a virtualenv or not aren't really within the sope of this
document.

In addition to the above, there are a number of Python requirements, all of
which are listed in ``requirements.txt``.  They will be installed automatically
with ``pip`` as part of the installation process.


.. _requirements-documentation:

Documentation
-------------

As generation of the documentation is not required for use of *Paperless*,
dependencies for this process are not included in ``requirements.txt``.  If
you'd like to generate your own docs locally, you'll need to:

.. code:: bash

    $ pip install sphinx

and then cd into the ``docs`` directory and type ``make html``.
