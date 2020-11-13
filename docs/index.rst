*********
Paperless
*********

Paperless is a simple Django application running in two parts:
a *Consumer* (the thing that does the indexing) and
the *Web server* (the part that lets you search &
download already-indexed documents). If you want to learn more about its
functions keep on reading after the installation section.


Why This Exists
===============

Paper is a nightmare.  Environmental issues aside, there's no excuse for it in
the 21st century.  It takes up space, collects dust, doesn't support any form
of a search feature, indexing is tedious, it's heavy and prone to damage &
loss.

I wrote this to make "going paperless" easier.  I do not have to worry about
finding stuff again. I feed documents right from the post box into the scanner
and then shred them.  Perhaps you might find it useful too.


Paperless-ng
============

I wanted to make big changes to the project that will impact the way it is used
by its users greatly. Among the users who currently use paperless in production
there are probably many that don't want these changes right away. I also wanted
to have more control over what goes into the code and what does not. Therefore,
paperless-ng was created. NG stands for both Angular (the framework used for the
Frontend) and next-gen. Publishing this project under a different name also
avoids confusion between paperless and paperless-ng.

It would be great if this project could eventually merge back into the main
repository, but it needs a lot more work before that can happen.


Contents
========

.. toctree::
   :maxdepth: 1

   setup
   usage_overview
   advanced_usage
   administration
   configuration
   api
   extending
   troubleshooting
   contributing
   scanners
   changelog
