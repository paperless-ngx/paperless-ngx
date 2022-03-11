.. _contributing:

Contributing to Paperless
#########################

.. warning::

    This section is not updated to paperless-ngx yet.

Maybe you've been using Paperless for a while and want to add a feature or two,
or maybe you've come across a bug that you have some ideas how to solve.  The
beauty of Free software is that you can see what's wrong and help to get it
fixed for everyone!


How to Get Your Changes Rolled Into Paperless
=============================================

If you've found a bug, but don't know how to fix it, you can always post an
issue on `GitHub`_ in the hopes that someone will have the time to fix it for
you.  If however you're the one with the time, pull requests are always
welcome, you just have to make sure that your code conforms to a few standards.

pre-commit Hooks
-----------------------

To ensure a consistent style and formatting across the project source, the project
utilizes a Git `pre-commit` hook to preform some formatting and linting before a
commit is allowed.  That way, everyone uses the same style and some common issues
can be caught early on.

The first time you are setting up to contribute, you'll need to install this hook.
If you've followed the initial development setup instructions, just run the following:

.. code:: shell-session

        pre-commit install

That's it!  The hooks will now run when you commit. If the formatting isn't quite right
or a linter catches something, the commit will be rejected.  You'll need to look at the
output and fix the issue.  Some hooks, such as the Python formatting tool `black`
will format failing files, so all you need to do is `git add` those files again and retry your
commit.


The Code of Conduct
===================

Paperless has a `code of conduct`_.  It's a lot like the other ones you see out
there, with a few small changes, but basically it boils down to:

> Don't be an ass, or you might get banned.

I'm proud to say that the CoC has never had to be enforced because everyone has
been awesome, friendly, and professional.

.. _GitHub: https://github.com/the-paperless-project/paperless/issues
.. _code of conduct: https://github.com/the-paperless-project/paperless/blob/master/CODE_OF_CONDUCT.md
