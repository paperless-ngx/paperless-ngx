
**************************
Frequently asked questions
**************************

**Q:** *What's the general plan for Paperless-ng?*

**A:** Paperless-ng is already almost feature-complete. This project will remain
as simple as it is right now. It will see improvements to features that are already there.
If you need advanced features such as document versions,
workflows or multi-user with customizable access to individual files, this is
not the tool for you.

Features that *are* planned are some more quality of life extensions for the searching
(i.e., search for similar documents, group results by correspondents with "more from this"
links, etc), bulk editing and hierarchical tags.

**Q:** *I'm using docker. Where are my documents?*

**A:** Your documents are stored inside the docker volume ``paperless_media``.
Docker manages this volume automatically for you. It is a persistent storage
and will persist as long as you don't explicitly delete it. The actual location
depends on your host operating system. On Linux, chances are high that this location
is

.. code::

    /var/lib/docker/volumes/paperless_media/_data

.. caution::

    Do not mess with this folder. Don't change permissions and don't move
    files around manually. This folder is meant to be entirely managed by docker
    and paperless.

**Q:** *Let's say you don't support this project anymore in a year. Can I easily move to other systems?*

**A:** Your documents are stored as plain files inside the media folder. You can always drag those files
out of that folder to use them elsewhere. Here are a couple notes about that.

*   Paperless never modifies your original documents. It keeps checksums of all documents and uses a
    scheduled sanity checker to check that they remain the same.
*   By default, paperless uses the internal ID of each document as its filename. This might not be very
    convenient for export. However, you can adjust the way files are stored in paperless by
    :ref:`configuring the filename format <advanced-file_name_handling>`.
*   :ref:`The exporter <utilities-exporter>` is another easy way to get your files out of paperless with reasonable file names.

**Q:** *What file types does paperless-ng support?*

**A:** Currently, the following files are supported:

*   PDF documents, PNG images, JPEG images, TIFF images and GIF images are processed with OCR and converted into PDF documents.
*   Plain text documents are supported as well and are added verbatim
    to paperless.

Paperless determines the type of a file by inspecting its content. The
file extensions do not matter.

**Q:** *Will paperless-ng run on Raspberry Pi?*

**A:** The short answer is yes. I've tested it on a Raspberry Pi 3 B.
The long answer is that certain parts of
Paperless will run very slow, such as the tesseract OCR. On Raspberry Pi,
try to OCR documents before feeding them into paperless so that paperless can
reuse the text. The web interface should be a lot snappier, since it runs
in your browser and paperless has to do much less work to serve the data.

.. note::
    
    You can adjust some of the settings so that paperless uses less processing
    power. See :ref:`setup-less_powerful_devices` for details.
    

**Q:** *How do I install paperless-ng on Raspberry Pi?*

**A:** There is no docker image for ARM available. If you know how to build
that automatically, I'm all ears. For now, you have to grab the latest release
archive from the project page and build the image yourself. The release comes
with the front end already compiled, so you don't have to do this on the Pi.

**Q:** *How do I run this on unRaid?*

**A:** Head over to `<https://github.com/selfhosters/unRAID-CA-templates>`_,
`Uli Fahrer <https://github.com/Tooa>`_ created a container template for that.
I don't exactly know how to use that though, since I don't use unRaid.

**Q:** *How do I run this on my toaster?*

**A:** I honestly don't know! As for all other devices that might be able
to run paperless, you're a bit on your own. If you can't run the docker image,
the documentation has instructions for bare metal installs. I'm running
paperless on an i3 processor from 2015 or so. This is also what I use to test
new releases with. Apart from that, I also have a Raspberry Pi, which I
occasionally build the image on and see if it works.

**Q:** *How do I proxy this with NGINX?*

.. code::

    location / {
        proxy_pass http://localhost:8000/
    }

And that's about it. Paperless serves everything, including static files by itself
when running the docker image. If you want to do anything fancy, you have to
install paperless bare metal.
