
**************************
Frequently asked questions
**************************

**Q:** *I'm using docker. Where are my documents?*

**A:** Your documents are stored inside the docker volume ``paperless_media``.
Docker manages this volume automatically for you. It is a persistent storage
and will persist as long as you don't explicitly delete it. The actual location
depends on your host operating system. On Linux, chances are high that this location
is

.. code::

    /var/lib/docker/volumes/paperless_media/_data

.. caution::

    Dont mess with this folder. Don't change permissions and don't move
    files around manually. This folder is meant to be entirely managed by docker
    and paperless.