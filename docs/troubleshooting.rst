***************
Troubleshooting
***************

No files are added by the consumer
##################################

Check for the following issues:

*   Ensure that the directory you're putting your documents in is the folder
    paperless is watching. With docker, this setting is performed in the
    ``docker-compose.yml`` file. Without docker, look at the ``CONSUMPTION_DIR``
    setting. Don't adjust this setting if you're using docker.
*   Ensure that redis is up and running. Paperless does its task processing
    asynchronously, and for documents to arrive at the task processor, it needs
    redis to run.
*   Ensure that the task processor is running. Docker does this automatically.
    Manually invoke the task processor by executing

    .. code:: shell-session

        $ python3 manage.py qcluster

*   Look at the output of paperless and inspect it for any errors.
*   Go to the admin interface, and check if there are failed tasks. If so, the
    tasks will contain an error message.


Consumer fails to pickup any new files
######################################

If you notice that the consumer will only pickup files in the consumption
directory at startup, but won't find any other files added later, check out
the configuration file and enable filesystem polling with the setting
``PAPERLESS_CONSUMER_POLLING``.

Operation not permitted
#######################

You might see errors such as:

.. code::

    chown: changing ownership of '../export': Operation not permitted

The container tries to set file ownership on the listed directories. This is
required so that the user running paperless inside docker has write permissions
to these folders. This happens when pointing these directories to NFS shares,
for example.

Ensure that `chown` is possible on these directories.
