.. _contributing:

Contributing to Paperless
#########################

.. warning::

    This section is not updated to paperless-ng yet.

Maybe you've been using Paperless for a while and want to add a feature or two,
or maybe you've come across a bug that you have some ideas how to solve.  The
beauty of Free software is that you can see what's wrong and help to get it
fixed for everyone!


How to Get Your Changes Rolled Into Paperless
=============================================

If you've found a bug, but don't know how to fix it, you can always post an
issue on `GitHub`_ in the hopes that someone will have the time to fix it for
you.  If however you're the one with the time, pull requests are always
welcome, you just have to make sure that your code conforms to a few standards:

Pep8
----

It's the standard for all Python development, so it's `very well documented`_.
The short version is:

* Lines should wrap at 79 characters
* Use ``snake_case`` for variables, ``CamelCase`` for classes, and ``ALL_CAPS``
  for constants.
* Space out your operators: ``stuff + 7`` instead of ``stuff+7``
* Two empty lines between classes, and functions, but 1 empty line between
  class methods.

There's more to it than that, but if you follow those, you'll probably be
alright.  When you submit your pull request, there's a pep8 checker that'll
look at your code to see if anything is off.  If it finds anything, it'll
complain at you until you fix it.


Additional Style Guides
-----------------------

Where pep8 is ambiguous, I've tried to be a little more specific.  These rules
aren't hard-and-fast, but if you can conform to them, I'll appreciate it and
spend less time trying to conform your PR before merging:


Function calls
..............

If you're calling a function and that necessitates more than one line of code,
please format it like this:

.. code:: python

    my_function(
        argument1,
        kwarg1="x",
        kwarg2="y"
        another_really_long_kwarg="some big value"
        a_kwarg_calling_another_long_function=another_function(
            another_arg,
            another_kwarg="kwarg!"
        )
    )

This is all in the interest of code uniformity rather than anything else.  If
we stick to a style, everything is understandable in the same way.


Quoting Strings
...............

pep8 is a little too open-minded on this for my liking.  Python strings should
be quoted with double quotes (``"``) except in cases where the resulting string
would require too much escaping of a double quote, in which case, a single
quoted, or triple-quoted string will do:

.. code:: python

    my_string = "This is my string"
    problematic_string = 'This is a "string" with "quotes" in it'

In HTML templates, please use double-quotes for tag attributes, and single
quotes for arguments passed to Django template tags:

.. code:: html

    <div class="stuff">
        <a href="{% url 'some-url-name' pk='w00t' %}">link this</a>
    </div>

This is to keep linters happy they look at an HTML file and see an attribute
closing the ``"`` before it should have been.

--

That's all there is in terms of guidelines, so I hope it's not too daunting.


Indentation & Spacing
.....................

When it comes to indentation:

* For Python, the rule is: follow pep8 and use 4 spaces.
* For Javascript, CSS, and HTML, please use 1 tab.

Additionally, Django templates making use of block elements like ``{% if %}``,
``{% for %}``, and ``{% block %}`` etc. should be indented:

Good:

.. code:: html

    {% block stuff %}
    	<h1>This is the stuff</h1>
    {% endblock %}

Bad:

.. code:: html

    {% block stuff %}
    <h1>This is the stuff</h1>
    {% endblock %}


The Code of Conduct
===================

Paperless has a `code of conduct`_.  It's a lot like the other ones you see out
there, with a few small changes, but basically it boils down to:

> Don't be an ass, or you might get banned.

I'm proud to say that the CoC has never had to be enforced because everyone has
been awesome, friendly, and professional.

.. _GitHub: https://github.com/the-paperless-project/paperless/issues
.. _very well documented: https://www.python.org/dev/peps/pep-0008/
.. _code of conduct: https://github.com/the-paperless-project/paperless/blob/master/CODE_OF_CONDUCT.md
