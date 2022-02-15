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


Paperless always redirects to /admin
####################################

You probably had the old paperless installed at some point. Paperless installed
a permanent redirect to /admin in your browser, and you need to clear your
browsing data / cache to fix that.


Operation not permitted
#######################

You might see errors such as:

.. code:: shell-session

    chown: changing ownership of '../export': Operation not permitted

The container tries to set file ownership on the listed directories. This is
required so that the user running paperless inside docker has write permissions
to these folders. This happens when pointing these directories to NFS shares,
for example.

Ensure that ``chown`` is possible on these directories.


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
in most cases. This warning will disappear automatically when paperless updates the training data.

If you want to get rid of the warning or actually experience issues with automatic matching, delete
the file ``classification_model.pickle`` in the data directory and let paperless recreate it.


504 Server Error: Gateway Timeout when adding Office documents
##############################################################

You may experience these errors when using the optional TIKA integration:

.. code::

    requests.exceptions.HTTPError: 504 Server Error: Gateway Timeout for url: http://gotenberg:3000/convert/office

Gotenberg is a server that converts Office documents into PDF documents and has a default timeout of 10 seconds.
When conversion takes longer, Gotenberg raises this error.

You can increase the timeout by configuring an environment variable for gotenberg (see also `here <https://thecodingmachine.github.io/gotenberg/#environment_variables.default_wait_timeout>`__).
If using docker-compose, this is achieved by the following configuration change in the ``docker-compose.yml`` file:

.. code:: yaml

    gotenberg:
        image: thecodingmachine/gotenberg
        restart: unless-stopped
        environment:
            DISABLE_GOOGLE_CHROME: 1
            DEFAULT_WAIT_TIMEOUT: 30

Permission denied errors in the consumption directory
#####################################################

You might encounter errors such as:

.. code:: shell-session

    The following error occured while consuming document.pdf: [Errno 13] Permission denied: '/usr/src/paperless/src/../consume/document.pdf'

This happens when paperless does not have permission to delete files inside the consumption directory.
Ensure that ``USERMAP_UID`` and ``USERMAP_GID`` are set to the user id and group id you use on the host operating system, if these are
different from ``1000``. See :ref:`setup-docker_hub`.

Also ensure that you are able to read and write to the consumption directory on the host.


OSError: [Errno 19] No such device when consuming files
#######################################################

If you experience errors such as:

.. code:: shell-session

    File "/usr/local/lib/python3.7/site-packages/whoosh/codec/base.py", line 570, in open_compound_file
    return CompoundStorage(dbfile, use_mmap=storage.supports_mmap)
    File "/usr/local/lib/python3.7/site-packages/whoosh/filedb/compound.py", line 75, in __init__
    self._source = mmap.mmap(fileno, 0, access=mmap.ACCESS_READ)
    OSError: [Errno 19] No such device

    During handling of the above exception, another exception occurred:

    Traceback (most recent call last):
    File "/usr/local/lib/python3.7/site-packages/django_q/cluster.py", line 436, in worker
    res = f(*task["args"], **task["kwargs"])
    File "/usr/src/paperless/src/documents/tasks.py", line 73, in consume_file
    override_tag_ids=override_tag_ids)
    File "/usr/src/paperless/src/documents/consumer.py", line 271, in try_consume_file
    raise ConsumerError(e)

Paperless uses a search index to provide better and faster full text searching. This search index is stored inside
the ``data`` folder. The search index uses memory-mapped files (mmap). The above error indicates that paperless
was unable to create and open these files.

This happens when you're trying to store the data directory on certain file systems (mostly network shares)
that don't support memory-mapped files.


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

Error while reading metadata
############################

You might find messages like these in your log files:

.. code::

    [WARNING] [paperless.parsing.tesseract] Error while reading metadata

This indicates that paperless failed to read PDF metadata from one of your documents. This happens when you
open the affected documents in paperless for editing. Paperless will continue to work, and will simply not
show the invalid metadata.
