*************
Configuration
*************

Paperless provides a wide range of customizations.
Have a look at ``paperless.conf.example`` for available configuration options.
Depending on how you run paperless, these settings have to be defined in different
places.

*   If you run paperless on docker, ``paperless.conf`` is not used. Rather, configure
    paperless by copying necessary options to ``docker-compose.env``.
*   If you are running paperless on anything else, paperless will search for the
    configuration file in these locations and use the first one it finds:

    .. code::

        /path/to/paperless/paperless.conf
        /etc/paperless.conf
        /usr/local/etc/paperless.conf

    Copy ``paperless.conf.example`` to any of these locations and adjust it to your
    needs.

.. warning::

    TBD: explain config options.