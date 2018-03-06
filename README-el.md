# Paperless

[![Documentation](https://readthedocs.org/projects/paperless/badge/?version=latest)](https://paperless.readthedocs.org/) [![Chat](https://badges.gitter.im/danielquinn/paperless.svg)](https://gitter.im/danielquinn/paperless) [![Travis](https://travis-ci.org/danielquinn/paperless.svg?branch=master)](https://travis-ci.org/danielquinn/paperless) [![Coverage Status](https://coveralls.io/repos/github/danielquinn/paperless/badge.svg?branch=master)](https://coveralls.io/github/danielquinn/paperless?branch=master)

Ευρετήριο και αρχείο για όλα σας τα σκαναρισμένα έγγραφα

Μισώ το χαρτί. Πέρα από τα περιβαλλοντικά ζητήματα, είναι ο εφιάλτης ενός τεχνικού.

* Δεν υπάρχει η δυνατότητα της αναζήτησης
* Πιάνουν πολύ χώρο
* Τα αντίγραφα ασφαλείας σημάινουν περισσότερο χαρτί

Τους τελευταίους μήνες μου έχει τύχει αρκετές φορές να μην μπορώ να βρω το σωστό έγγραφο. Κάποιες φορές ανακύκλωνα το έγγραφο που χρειαζόμουν (ποιος κρατάει τους λογαριασμούς του νερού για 2 χρόνια;;;) και κάποιες φορές απλά το έχανα ... επειδή έτσι είναι τα χαρτιά. Το έκανα αυτό για να κάνω την ζωή μου πιο εύκολη


## Πως δουλεύει

Paperless does not control your scanner, it only helps you deal with what your scanner produces

1. Buy a document scanner that can write to a place on your network.  If you need some inspiration, have a look at the [scanner recommendations](https://paperless.readthedocs.io/en/latest/scanners.html) page.
2. Set it up to "scan to FTP" or something similar. It should be able to push scanned images to a server without you having to do anything.  Of course if your scanner doesn't know how to automatically upload the file somewhere, you can always do that manually.  Paperless doesn't care how the documents get into its local consumption directory.
3. Have the target server run the Paperless consumption script to OCR the file and index it into a local database.
4. Use the web frontend to sift through the database and find what you want.
5. Download the PDF you need/want via the web interface and do whatever you like with it.  You can even print it and send it as if it's the original. In most cases, no one will care or notice.

Here's what you get:

![The before and after](https://raw.githubusercontent.com/danielquinn/paperless/master/docs/_static/screenshot.png)


## Documentation

It's all available on [ReadTheDocs](https://paperless.readthedocs.org/).


## Requirements

This is all really a quite simple, shiny, user-friendly wrapper around some very powerful tools.

* [ImageMagick](http://imagemagick.org/) converts the images between colour and greyscale.
* [Tesseract](https://github.com/tesseract-ocr) does the character recognition.
* [Unpaper](https://www.flameeyes.eu/projects/unpaper) despeckles and deskews the scanned image.
* [GNU Privacy Guard](https://gnupg.org/) is used as the encryption backend.
* [Python 3](https://python.org/) is the language of the project.
  * [Pillow](https://pypi.python.org/pypi/pillowfight/) loads the image data as a python object to be used with PyOCR.
  * [PyOCR](https://github.com/jflesch/pyocr) is a slick programmatic wrapper around tesseract.
  * [Django](https://www.djangoproject.com/) is the framework this project is written against.
  * [Python-GNUPG](http://pythonhosted.org/python-gnupg/) decrypts the PDFs on-the-fly to allow you to download unencrypted files, leaving the encrypted ones on-disk.


## Σταθερότητα

This project has been around since 2015, and there's lots of people using it, however it's still under active development (just look at the git commit history) so don't expect it to be 100% stable.  You can backup the sqlite3 database, media directory and your configuration file to be on the safe side.


## Affiliated Projects

Paperless has been around a while now, and people are starting to build stuff on top of it.  If you're one of those people, we can add your project to this list:

* [Paperless Desktop](https://github.com/thomasbrueggemann/paperless-desktop): A desktop UI for your Paperless installation.  Runs on Mac, Linux, and Windows.
* [ansible-role-paperless](https://github.com/ovv/ansible-role-paperless): An easy way to get Paperless running via Ansible.


## Παρόμοια Projects

There's another project out there called [Mayan EDMS](https://mayan.readthedocs.org/en/latest/) that has a surprising amount of technical overlap with Paperless.  Also based on Django and using a consumer model with Tesseract and Unpaper, Mayan EDMS is *much* more featureful and comes with a slick UI as well, but still in Python 2. It may be that Paperless consumes fewer resources, but to be honest, this is just a guess as I haven't tested this myself.  One thing's for certain though, *Paperless* is a **way** better name.


## Σημαντική Σημείωση

Document scanners are typically used to scan sensitive documents.  Things like your social insurance number, tax records, invoices, etc.  While Paperless encrypts the original files via the consumption script, the OCR'd text is *not* encrypted and is therefore stored in the clear (it needs to be searchable, so if someone has ideas on how to do that on encrypted data, I'm all ears).  This means that Paperless should never be run on an untrusted host.  Instead, I recommend that if you do want to use it, run it locally on a server in your own home.


## Δωρεές

As with all Free software, the power is less in the finances and more in the collective efforts.  I really appreciate every pull request and bug report offered up by Paperless' users, so please keep that stuff coming.  If however, you're not one for coding/design/documentation, and would like to contribute financially, I won't say no ;-)

The thing is, I'm doing ok for money, so I would instead ask you to donate to the [United Nations High Commissioner for Refugees](https://donate.unhcr.org/int-en/general). They're doing important work and they need the money a lot more than I do.
