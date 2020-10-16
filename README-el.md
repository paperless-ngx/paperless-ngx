[ [en](README.md) | [de](README-de.md) | el ]

![Paperless](https://raw.githubusercontent.com/the-paperless-project/paperless/master/src/paperless/static/paperless/img/logo-dark.png)

[![Documentation](https://readthedocs.org/projects/paperless/badge/?version=latest)](https://paperless.readthedocs.org/) [![Chat](https://badges.gitter.im/the-paperless-project/paperless.svg)](https://gitter.im/danielquinn/paperless) [![Travis](https://travis-ci.org/the-paperless-project/paperless.svg?branch=master)](https://travis-ci.org/the-paperless-project/paperless) [![Coverage Status](https://coveralls.io/repos/github/the-paperless-project/paperless/badge.svg?branch=master)](https://coveralls.io/github/the-paperless-project/paperless?branch=master) [![Thanks](https://img.shields.io/badge/THANKS-md-ff69b4.svg)](https://github.com/the-paperless-project/paperless/blob/master/THANKS.md)

Ευρετήριο και αρχείο για όλα σας τα σκαναρισμένα έγγραφα

Μισώ το χαρτί. Πέρα από τα περιβαλλοντικά ζητήματα, είναι ο εφιάλτης ενός τεχνικού.

* Δεν υπάρχει η δυνατότητα της αναζήτησης
* Πιάνουν πολύ χώρο
* Τα αντίγραφα ασφαλείας σημάινουν περισσότερο χαρτί

Τους τελευταίους μήνες μου έχει τύχει αρκετές φορές να μην μπορώ να βρω το σωστό έγγραφο. Κάποιες φορές ανακύκλωνα το έγγραφο που χρειαζόμουν (ποιος κρατάει τους λογαριασμούς του νερού για 2 χρόνια;;;) και κάποιες φορές απλά το έχανα ... επειδή έτσι είναι τα χαρτιά. Το έκανα αυτό για να κάνω την ζωή μου πιο εύκολη


## Πως δουλεύει

Η εφαρμογή Paperless δεν ελέγχει το scanner σας, αλλά σας βοηθάει με τα αποτελέσματα του scanner σας.

1. Αγοράστε ένα scanner με πρόσβαση στο δίκτυο σας.  Αν χρειάζεστε έμπνευση, δείτε την σελίδα με τα [προτεινόμενα scanner](https://paperless.readthedocs.io/en/latest/scanners.html).
2. Κάντε την ρύθμιση "scan to FTP" ή κάτι παρόμοιο. Θα μπορεί να αποθηκεύει τις σκαναρισμένες εικόνες σε έναν server χωρίς να χρειάζεται να κάνετε κάτι. Φυσικά άμα το scanner σας δεν μπορεί να αποθηκεύσει κάπου τις εικόνες σας αυτόματα μπορείτε να το κάνετε χειροκίνητα. Το Paperless δεν ενδιαφέρεται πως καταλήγουν κάπου τα αρχεία.
3. Να έχετε τον server που τρέχει το OCR script του Paperless να έχει ευρετήριο στην τοπική βάση δεδομένων.
4. Χρησιμοποιήστε το web frontend για να επιλέξετε βάση δεδομένων και να βρείτε αυτό που θέλετε.
5. Κατεβάστε το PDF που θέλετε/χρειάζεστε μέσω του web interface και κάντε ότι θέλετε με αυτό. Μπορείτε ακόμη να το εκτυπώσετε και να το στείλετε, σαν να ήταν το αρχικό. Στις περισσότερες περιπτώσεις κανείς δεν θα το προσέξει ή θα νοιαστεί.

Αυτό είναι που θα πάρετε:

![Το πριν και το μετά](https://raw.githubusercontent.com/the-paperless-project/paperless/master/docs/_static/screenshot.png)


## Documentation

Είναι όλα διαθέσιμα εδώ [ReadTheDocs](https://paperless.readthedocs.org/).


## Απαιτήσεις

Όλα αυτά είναι πολύ απλά, και φιλικά προς τον χρήστη, μια συλλογή με πολύτιμα εργαλεία.

* [ImageMagick](http://imagemagick.org/) μετατρέπει τις εικόνες σε έγχρωμες και ασπρόμαυρες.
* [Tesseract](https://github.com/tesseract-ocr) κάνει την αναγνώρηση των χαρακτήρων.
* [Unpaper](https://github.com/unpaper/unpaper) despeckles and deskews the scanned image.
* [GNU Privacy Guard](https://gnupg.org/) χρησιμοποιείται για κρυπτογράφηση στο backend.
* [Python 3](https://python.org/) είναι η γλώσσα του project.
  * [Pillow](https://pypi.python.org/pypi/pillowfight/) Φορτώνει την εικόνα σαν αντικείμενο στην python και μπορεί να χρησιμοποιηθεί με PyOCR
  * [PyOCR](https://github.com/jflesch/pyocr) is a slick programmatic wrapper around tesseract.
  * [Django](https://www.djangoproject.com/) το framework με το οποίο έγινε το project.
  * [Python-GNUPG](http://pythonhosted.org/python-gnupg/) Αποκρυπτογραφεί τα PDF αρχεία στη στιγμή ώστε να κατεβάζετε αποκρυπτογραφημένα αρχεία, αφήνοντας τα κρυπτογραφημένα στον δίσκο.


## Σταθερότητα

Αυτό το project υπάρχει από το 2015 και υπάρχουν αρκετοί άνθρωποι που το χρησιμοποιούν, παρόλα αυτά βρίσκεται σε διαρκή ανάπτυξη (απλά δείτε πότε commit έχουν γίνει στο git history) οπότε μην περιμένετε να είναι 100% σταθερό. Μπορείτε να κάνετε backup την βάση δεδομένων sqlite3, τον φάκελο media και το configuration αρχείο σας ώστε να είστε ασφαλείς.


## Affiliated Projects

Το Paperless υπάρχει εδώ και κάποιο καιρό και άνθρωποι έχουν αρχίσει να φτιάχνουν πράγματα γύρω από αυτό. Αν είσαι ένας από αυτούς τους ανθρώπους, μπορούμε να βάλουμε το project σου σε αυτήν την λίστα:

* [Paperless App](https://github.com/bauerj/paperless_app): Μια εφαρμογή Android / iOS για Paperless.
* [Paperless Desktop](https://github.com/thomasbrueggemann/paperless-desktop): Μια desktop εφαρμογή για εγκατάσταση του Paperless.  Τρέχει σε Mac, Linux, και Windows.
* [ansible-role-paperless](https://github.com/ovv/ansible-role-paperless): Ένας εύκολο τρόπος για να τρέχει το Paperless μέσω Ansible.


## Παρόμοια Projects

Υπάρχει ένα άλλο ṕroject που λέγεται [Mayan EDMS](https://mayan.readthedocs.org/en/latest/) το οποίο έχει παρόμοια τεχνικά χαρακτηριστικά με το Paperless σε εντυπωσιακό βαθμό.  Επίσης βασισμένο στο Django και χρησιμοποιώντας το consumer model με Tesseract και Unpaper, Mayan EDMS έχει *πολλά* περισσότερα χαρακτηριστικά και έρχεται με ένα επιδέξιο UI, αλλά είναι ακόμα σε Python 2. Μπορεί να είναι ότι το Paperless καταναλώνει λιγότερους πόρους, αλλά για να είμαι ειλικρινής, αυτό είναι μια εικασία την οποία δεν έχω επιβεβαιώσει μόνος μου.  Ένα πράγμα είναι σίγουρο, το *Paperless* έχει **πολύ** καλύτερο όνομα.


## Σημαντική Σημείωση

Τα scanner για αρχεία συνήθως χρησιμοποιούνται για ευαίσθητα αρχεία. Πράγματα όπως το ΑΜΚΑ, φορολογικά αρχεία, τιμολόγια κτλπ. Παρόλο που το Paperless κρυπτογραφεί τα αρχικά αρχεία μέσω του consumption script, το κείμενο OCR *δεν είναι* κρυπτογραφημένο και για αυτό αποθηκεύεται (πρέπει να είναι αναζητήσιμο, οπότε αν κάποιος ξέρει να το κάνει αυτό με κρυπτογραφημένα δεδομένα είμαι όλος αυτιά). Αυτό σημάνει ότι το Paperless δεν πρέπει ποτέ να τρέχει σε μη αξιόπιστο πάροχο. Για αυτό συστήνω αν θέλετε να το τρέξετε να το τρέξετε σε έναν τοπικό server σπίτι σας.


## Δωρεές

Όπως με όλα τα δωρεάν λογισμικά, η δύναμη δεν βρίσκεται στα οικονομικά αλλά στην συλλογική προσπάθεια. Αλήθεια εκτιμώ κάθε pull request και bug report που προσφέρεται από τους χρήστες του Paperless, οπότε σας παρακαλώ συνεχίστε. Αν παρόλα αυτά, δεν μπορείτε να γράψετε κώδικα/να κάνέτε design/να γράψετε documentation, και θέλετε να συνεισφέρετε οικονομικά, δεν θα πω όχι ;-)

Το θέμα είναι ότι είμαι οικονομικά εντάξει, οπότε θα σας ζητήσω να δωρίσετε τα χρήματα σας εδώ [United Nations High Commissioner for Refugees](https://donate.unhcr.org/int-en/general). Κάνουν σημαντική δουλειά και χρειάζονται τα χρήματα πολύ περισσότερο από ότι εγώ.
