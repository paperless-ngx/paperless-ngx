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

.. code:: shell-session

    chown: changing ownership of '../export': Operation not permitted

The container tries to set file ownership on the listed directories. This is
required so that the user running paperless inside docker has write permissions
to these folders. This happens when pointing these directories to NFS shares,
for example.

Ensure that `chown` is possible on these directories.

Classifier error: No training data available
############################################

This indicates that the Auto matching algorithm found no documents to learn from.
This may have two reasons:

*   You don't use the Auto matching algorithm: The error can be safely ignored in this case.
*   You are using the Auto matching algorithm: The classifier explicitly excludes documents
    with Inbox tags. Verify that there are documents in your archive without inbox tags.
    The algorithm will only learn from documents not in your inbox.

Permission denied errors in the consumption directory
#####################################################

You might encounter errors such as:

.. code:: shell-session

    The following error occured while consuming document.pdf: [Errno 13] Permission denied: '/usr/src/paperless/src/../consume/document.pdf'

This happens when paperless does not have permission to delete files inside the consumption directory.
Ensure that ``USERMAP_UID`` and ``USERMAP_GID`` are set to the user id and group id you use on the host operating system, if these are
different from ``1000``. See :ref:`setup-docker_route`.

Also ensure that you are able to read and write to the consumption directory on the host.
