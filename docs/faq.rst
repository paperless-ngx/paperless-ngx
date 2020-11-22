
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

**Q:** *What file types does paperless-ng support?*

**A:** Currently, the following files are supported:

*   PDF documents, PNG images and JPEG images are processed with OCR.
*   Plain text documents are supported as well and are added verbatim
    to paperless.

Paperless determines the type of a file by inspecting its content. The
file extensions do not matter.

**Q:** *Will paperless-ng run on Raspberry Pi?*

**A:** The short answer is yes. I've tested it on a Raspberry Pi 3 B.
The long answer is that certain parts of
Paperless will run very slow, such as the tesseract OCR. On Rasperry Pi,
try to OCR documents before feeding them into paperless so that paperless can
reuse the text. The web interface should be alot snappier, since it runs
in your browser and paperless has to do much less work to serve the data.

.. note::
    
    You can adjust some of the settings so that paperless uses less processing
    power. See :ref:`setup-less_powerful_devices` for details.
    

**Q:** *How do I install paperless-ng on Raspberry Pi?*

**A:** There is not docker image for ARM available. If you know how to build
that automatically, I'm all ears. For now, you have to grab the latest release
archive from the project page and build the image yourself. The release comes
with the front end already compiled, so you don't have to do this on the Pi.
