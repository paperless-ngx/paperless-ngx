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
directory at startup, but won't find any other files added later, you will need to
enable filesystem polling with the configuration option
``PAPERLESS_CONSUMER_POLLING``, see :ref:`here <configuration-polling>`.

This will disable listening to filesystem changes with inotify and paperless will
manually check the consumption directory for changes instead.

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

UserWarning in sklearn on every single document
###############################################

You may encounter warnings like this:

.. code::
    
    /usr/local/lib/python3.7/site-packages/sklearn/base.py:315:
    UserWarning: Trying to unpickle estimator CountVectorizer from version 0.23.2 when using version 0.24.0.
    This might lead to breaking code or invalid results. Use at your own risk.

This happens when certain dependencies of paperless that are responsible for the auto matching algorithm are
updated. After updating these, your current training data *might* not be compatible anymore. This can be ignored
in most cases. If you want to get rid of the warning or actually experience issues with automatic matching, delete
the file ``classification_model.pickle`` in the data directory and let paperless recreate it.

Permission denied errors in the consumption directory
#####################################################

You might encounter errors such as:

.. code:: shell-session

    The following error occured while consuming document.pdf: [Errno 13] Permission denied: '/usr/src/paperless/src/../consume/document.pdf'

This happens when paperless does not have permission to delete files inside the consumption directory.
Ensure that ``USERMAP_UID`` and ``USERMAP_GID`` are set to the user id and group id you use on the host operating system, if these are
different from ``1000``. See :ref:`setup-docker_hub`.

Also ensure that you are able to read and write to the consumption directory on the host.

Web-UI stuck at "Loading..."
############################

This might have multiple reasons.


1.  If you built the docker image yourself or deployed using the bare metal route,
    make sure that there are files in ``<paperless-root>/static/frontend/<lang-code>/``.
    If there are no files, make sure that you executed ``collectstatic`` successfully, either
    manually or as part of the docker image build.

    If the front end is still missing, make sure that the front end is compiled (files present in
    ``src/documents/static/frontend``). If it is not, you need to compile the front end yourself
    or download the release archive instead of cloning the repository.

2.  Check the output of the web server. You might see errors like this:


    .. code::

        [2021-01-25 10:08:04 +0000] [40] [ERROR] Socket error processing request.
        Traceback (most recent call last):
        File "/usr/local/lib/python3.7/site-packages/gunicorn/workers/sync.py", line 134, in handle
            self.handle_request(listener, req, client, addr)
        File "/usr/local/lib/python3.7/site-packages/gunicorn/workers/sync.py", line 190, in handle_request
            util.reraise(*sys.exc_info())
        File "/usr/local/lib/python3.7/site-packages/gunicorn/util.py", line 625, in reraise
            raise value
        File "/usr/local/lib/python3.7/site-packages/gunicorn/workers/sync.py", line 178, in handle_request
            resp.write_file(respiter)
        File "/usr/local/lib/python3.7/site-packages/gunicorn/http/wsgi.py", line 396, in write_file
            if not self.sendfile(respiter):
        File "/usr/local/lib/python3.7/site-packages/gunicorn/http/wsgi.py", line 386, in sendfile
            sent += os.sendfile(sockno, fileno, offset + sent, count)
        OSError: [Errno 22] Invalid argument
    
    To fix this issue, add

    .. code::

        SENDFILE=0
    
    to your `docker-compose.env` file.