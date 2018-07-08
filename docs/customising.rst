.. _customising:

Customising Paperless
#####################

Currently, the Paperless' interface is just the default Django admin, which
while powerful, is rather boring.  If you'd like to give the site a bit of a
face-lift, or if you simply want to adjust the colours, contrast, or font size
to make things easier to read, you can do that by adding your own CSS or
Javascript quite easily.


.. _customising-overrides:

Overrides
=========

On every page load, Paperless looks for two files in your media root directory
(the directory defined by your ``PAPERLESS_MEDIADIR`` configuration variable or
the default, ``<project root>/media/``) for two files:

* ``overrides.css``
* ``overrides.js``

If it finds either or both of those files, they'll be loaded into the page: the
CSS in the ``<head>``, and the Javascript stuffed into the last line of the
``<body>``.


.. _customising-overrides-note:

An important note about customisation
-------------------------------------

Any changes you make to the site with your CSS or Javascript are likely to
depend on the structure of the current HTML and/or the existing CSS rules.  For
the most part it's safe to assume that these bits won't change, but *sometimes
they do* as features are added or bugs are fixed.

If you make a change that you think others would appreciate though, submit it
as a pull request and maybe we can find a way to work it into the project by
default!