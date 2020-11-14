
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

**Q:** *Will paperless-ng run on Raspberry Pi?*

**A:** The short answer is yes. The long answer is that certain parts of
Paperless will run very slow, such as the tesseract OCR. On Rasperry Pi,
try to OCR documents before feeding them into paperless so that paperless can
reuse the text. The web interface should be alot snappier, since it runs
in your browser and paperless has to do much less work to serve the data.

**Q:** *How do I install paperless-ng on Raspberry Pi?*

**A:** There is not docker image for ARM available. If you know how to build
that automatically, I'm all ears. For now, you have to grab the latest release
archive from the project page and build the image yourself. The release comes
with the front end already compiled, so you don't have to do this on the Pi.

You may encounter some issues during the build:

.. code:: shell-session

    W: GPG error: http://ports.ubuntu.com/ubuntu-ports focal InRelease: At least one invalid signature was encountered.
    E: The repository 'http://ports.ubuntu.com/ubuntu-ports focal InRelease' is not signed.
    N: Updating from such a repository can't be done securely, and is therefore disabled by default.
    N: See apt-secure(8) manpage for repository creation and user configuration details.

If this happens, look at `this thread <https://askubuntu.com/questions/1263284/>`:_.
You will need to update docker to the latest version to fix this issue.
