# paperless
Scan, index, and archive all of your paper documents

I hate paper.  Environmental issues aside, it's a tech person's nightmare:

* There's no search feature
* It takes up physical space
* Backups mean more paper

In the past few months I've been bitten more than a few times by the problem
of not having the right document around.  Sometimes I recycled a document I
needed (who keeps water bills for two years?) and other times I just lost
it... because paper.  I wrote this to make my life easier.

## How it Works:

1. Buy a document scanner like [this one](http://welcome.brother.com/sg-en/products-services/scanners/ads-1100w.html).
2. Set it up to "scan to FTP" or something similar. It should be able to push
   scanned images to a server without you having to do anything.
3. Have the target server run the *paperless* consumption script to OCR the PDF
   and index it into a local database.
4. Use the web frontend to sift through the database and find what you want.
5. Download the PDF you need/want via the web interface and do whatever you
   like with it.  You can even print it and send it as if it's the original.
   In most cases, no one will care or notice.


## Requirements

This is all really a quite simple, shiny, user-friendly wrapper around some very
powerful tools.

* [ImageMagick](http://imagemagick.org/) converts the images between colour and
  greyscale.
* [Tesseract](https://github.com/tesseract-ocr) does the character recognition
* [GNU Privacy Guard](https://gnupg.org)
* [Python 3](https://python.org/) is the language of the project
    * [Pillow](https://pypi.python.org/pypi/pillowfight/) converts the PDFs to
      images
    * [PyOCR](https://github.com/jflesch/pyocr) is a slick programmatic wrapper
      around tesseract
    * [Django](https://djangoproject.org/) is the framework this project is 
      written against.
    * [Python-GNUPG](http://pythonhosted.org/python-gnupg/)


## Instructions

1. Check out this repo to somewhere convenient and install the requirements
   listed here into your environment.

2. Configure `settings.py` and make sure that `CONVERT_BINARY`, `SCRATCH_DIR`,
   and `CONSUMPTION_DIR` are set to values you'd expect:

    * `CONVERT_BINARY`: The path to `convert`, installed as part of ImageMagick.
    * `SCRATCH_DIR`: A place for files to be created and destroyed.  The default
      is as good a place as any.
    * `CONSUMPTION_DIR`: The directory you scanner will be depositing files.
      Note that the consumption script will import files from here **and then
      delete them**.

3. Run `python manage.py migrate`.  This will create your local database.

4. Run `python manage.py consume` and enter your preferred passphrase when
   prompted.

5. Start the webserver with `python manage.py runserver` and enter the same
   passphrase when prompted.

6. Log into your new toy by visiting `http://localhost:8000/`.
