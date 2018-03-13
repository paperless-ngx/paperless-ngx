# Paperless

[![Documentation](https://readthedocs.org/projects/paperless/badge/?version=latest)](https://paperless.readthedocs.org/) [![Chat](https://badges.gitter.im/danielquinn/paperless.svg)](https://gitter.im/danielquinn/paperless) [![Travis](https://travis-ci.org/danielquinn/paperless.svg?branch=master)](https://travis-ci.org/danielquinn/paperless) [![Coverage Status](https://coveralls.io/repos/github/danielquinn/paperless/badge.svg?branch=master)](https://coveralls.io/github/danielquinn/paperless?branch=master)

Ευρετήριο και αρχείο για όλα σας τα σκαναρισμένα έγγραφα

Μισώ το χαρτί. Πέρα από τα περιβαλλοντικά ζητήματα, είναι ο εφιάλτης ενός τεχνικού.

* Δεν υπάρχει η δυνατότητα της αναζήτησης
* Πιάνουν πολύ χώρο
* Τα αντίγραφα ασφαλείας σημάινουν περισσότερο χαρτί

Τους τελευταίους μήνες μου έχει τύχει αρκετές φορές να μην μπορώ να βρω το σωστό έγγραφο. Κάποιες φορές ανακύκλωνα το έγγραφο που χρειαζόμουν (ποιος κρατάει τους λογαριασμούς του νερού για 2 χρόνια;;;) και κάποιες φορές απλά το έχανα ... επειδή έτσι είναι τα χαρτιά. Το έκανα αυτό για να κάνω την ζωή μου πιο εύκολη


## Πως δουλεύει

Η εφαρμογή Paperless δεν ελέγχει το scanner σας, αλλά σας βοηθάει με τα αποτελέσματα του scanner σας.

1. Buy a document scanner that can write to a place on your network.  If you need some inspiration, have a look at the [scanner recommendations](https://paperless.readthedocs.io/en/latest/scanners.html) page.
2. Set it up to "scan to FTP" or something similar. It should be able to push scanned images to a server without you having to do anything.  Of course if your scanner doesn't know how to automatically upload the file somewhere, you can always do that manually.  Paperless doesn't care how the documents get into its local consumption directory.
3. Have the target server run the Paperless consumption script to OCR the file and index it into a local database.
4. Use the web frontend to sift through the database and find what you want.
5. Download the PDF you need/want via the web interface and do whatever you like with it.  You can even print it and send it as if it's the original. In most cases, no one will care or notice.

Αυτό είναι που θα πάρετε:

![Το πριν και το μετά](https://raw.githubusercontent.com/danielquinn/paperless/master/docs/_static/screenshot.png)


## Documentation

Είναι όλα διαθέσιμα εδώ [ReadTheDocs](https://paperless.readthedocs.org/).


## Απαιτήσεις

Όλα αυτά είναι πολύ απλά, και φιλικά προς τον χρήστη, μια συλλογή με πολύτιμα εργαλεία.

* [ImageMagick](http://imagemagick.org/) μετατρέπει τις εικόνες σε έγχρωμες και ασπρόμαυρες.
* [Tesseract](https://github.com/tesseract-ocr) κάνει την αναγώρηση των χαρακτήρων.
* [Unpaper](https://www.flameeyes.eu/projects/unpaper) despeckles and deskews the scanned image.
* [GNU Privacy Guard](https://gnupg.org/) χρησιμοποιείται για κρυπτογράφηση στο backend.
* [Python 3](https://python.org/) είναι η γλώσσα του project.
  * [Pillow](https://pypi.python.org/pypi/pillowfight/) Φορτώνει την εικόνα σαν αντικείμενο στην python και μπορεί να χρησιμοποιηθεί με PyOCR
  * [PyOCR](https://github.com/jflesch/pyocr) is a slick programmatic wrapper around tesseract.
  * [Django](https://www.djangoproject.com/) το framework με το οποίο έγινε το project.
  * [Python-GNUPG](http://pythonhosted.org/python-gnupg/) Αποκρυπτογραφεί τα PDF αρχεία στη στιγμή ώστε να κατεβάζετε αποκρυπτογραφημένα αρχεία, αφήνωντας τα κρυπτογραφημένα στον δίσκο.


## Σταθερότητα

Αυτό το project υπάρχει από το 2015 και υπάρχουν αρκετοί άνθρωποι που το χρησιμοποιούν, παρόλα αυτά βρίσκεται σε διαρκή ανάπτυξη (απλά δείτε πότε commit έχουν γίνει στο git history) οπότε μην περιμένετε να είναι 100% σταθερό. Μπορείτε να κάνετε backup την βάση δεδομένων sqlite3, τον φάκελο media και το configuration αρχείο σας ώστε να είστε ασφαλείς.


## Affiliated Projects

Το Paperless υπάρχει εδώ και κάποιο καιρό και άνθρωποι έχουν αρχήσει να φτιάχνουν πράγματα γύρω από αυτό. Αν είσαι ένας από αυτούς τους ανθρώπους, μπορούμε να βάλουμε το project σου σε αυτήν την λίστα:

* [Paperless Desktop](https://github.com/thomasbrueggemann/paperless-desktop): A desktop UI for your Paperless installation.  Runs on Mac, Linux, and Windows.
* [ansible-role-paperless](https://github.com/ovv/ansible-role-paperless): An easy way to get Paperless running via Ansible.


## Παρόμοια Projects

There's another project out there called [Mayan EDMS](https://mayan.readthedocs.org/en/latest/) that has a surprising amount of technical overlap with Paperless.  Also based on Django and using a consumer model with Tesseract and Unpaper, Mayan EDMS is *much* more featureful and comes with a slick UI as well, but still in Python 2. It may be that Paperless consumes fewer resources, but to be honest, this is just a guess as I haven't tested this myself.  One thing's for certain though, *Paperless* is a **way** better name.


## Σημαντική Σημείωση

Τα scanner για αρχεία συνήθως χρησιμοποιούνται για ευαίσθητα αρχεία. Πράγματα όπως το ΑΜΚΑ, φορολογικά αρχεία, τιμολόγια κτλπ. Παρόλο που το Paperless κρυπτογραφεί τα αρχικά αρχεία μέσω του consumption script, το κείμενο OCR * δεν είναι* κρυπρογραφημένο και για αυτό αποθηκεύεται (πρέπει να είναι αναζητήσιμο, οπότε αν κάποιος ξέρει να το κάνει αυτό με κρυπτογραφημένα δεδομένα είμαι όλος αυτιά). Αυτό σημάνει ότι το Paperless δεν πρέπει ποτέ να τρέχει σε μη αξιόπιστο πάροχο. Για αυτό συστήνω αν θέλετε να το τρέξετε να το τρέξετε σε έναν τοπικό server σπίτι σας.


## Δωρεές

Όπως με όλα τα δωρεάν λογισμικά, η δύναμη δεν βρίσκεται στα οικονομικά αλλά στην συλλογική προσπάθεια. Αλήθεια εκτιμώ κάθε pull request και bug report που προσφέρεται από τους χρήστες του Paperless, οπότε σας παρακαλώ συνεχίστε. Αν παρόλα αυτά, δεν μπορείτε να γράψετε κώδικα/να κάνέτε design/να γράψετε documentation, και θέλετε να συνεισφέρετε οικονομικά, δεν θα πω όχι ;-)

Το θέμα είναι ότι είμαι οικονομικά εντάξει, οπότε θα σας ζητήσω να δωρίσετε τα χρήματα σας εδώ [United Nations High Commissioner for Refugees](https://donate.unhcr.org/int-en/general). Κάνουν σημαντική δουλειά και χρειάζονται τα χρήματα πολύ περισσότερο από ότι εγώ.
