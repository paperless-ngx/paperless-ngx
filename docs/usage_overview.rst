**************
Usage Overview
**************

Paperless is an application that manages your personal documents. With
the help of a document scanner (see :ref:`scanners`), paperless transforms
your wieldy physical document binders into a searchable archive and
provices many utilities for finding and managing your documents.


Terms and definitions
#####################

Paperless esentially consists of two different parts for managing your
documents:

* The *consumer* watches a specified folder and adds all documents in that
  folder to paperless.
* The *web server* provides a UI that you use to manage and search for your
  scanned documents.

Each document has a couple of fields that you can assign to them:

* A *Document* is a piece of paper that sometimes contains valuable
  information.
* The *correspondent* of a document is the person, institution or company that
  a document either originates form, or is sent to.
* A *tag* is a label that you can assign to documents. Think of labels as more
  powerful folders: Multiple documents can be grouped together with a single
  tag, however, a single document can also have multiple tags. This is not
  possible with folders. The reason folders are not implemented in paperless
  is simply that tags are much more versatile than folders.
* A *document type* is used to demarkate the type of a document such as letter,
  bank statement, invoice, contract, etc. It is used to identify what a document
  is about.
* The *date added* of a document is the date the document was scanned into
  paperless. You cannot and should not change this date.
* The *date created* of a document is the date the document was intially issued.
  This can be the date you bought a product, the date you signed a contract, or
  the date a letter was sent to you.
* The *archive serial number* (short: ASN) of a document is the identifier of
  the document in your physical document binders. See
  :ref:`usage-recommended_workflow` below.
* The *content* of a document is the text that was OCR'ed from the document.
  This text is fed into the search engine and is used for matching tags,
  correspondents and document types.


Frontend overview
#################

.. warning::

    TBD. Add some fancy screenshots!

Adding documents to paperless
#############################

Once you've got Paperless setup, you need to start feeding documents into it.
Currently, there are three options: the consumption directory, IMAP (email), and
HTTP POST.


The consumption directory
=========================

The primary method of getting documents into your database is by putting them in
the consumption directory.  The consumer runs in an infinite
loop looking for new additions to this directory and when it finds them, it goes
about the process of parsing them with the OCR, indexing what it finds, and storing
it in the media directory.

Getting stuff into this directory is up to you.  If you're running Paperless
on your local computer, you might just want to drag and drop files there, but if
you're running this on a server and want your scanner to automatically push
files to this directory, you'll need to setup some sort of service to accept the
files from the scanner.  Typically, you're looking at an FTP server like
`Proftpd`_ or a Windows folder share with `Samba`_.

.. _Proftpd: http://www.proftpd.org/
.. _Samba: http://www.samba.org/

.. TODO: hyperref to configuration of the location of this magic folder.

.. _usage-email:

IMAP (Email)
============

You can tell paperless-ng to consume documents from your email accounts.
This is a very flexible and powerful feature, if you regularly received documents
via mail that you need to archive. The mail consumer can be configured by using the
admin interface in the following manner:

1.  Define e-mail accounts.
2.  Define mail rules for your account.

These rules perform the following:

1.  Connect to the mail server.
2.  Fetch all matching mails (as defined by folder, maximum age and the filters)
3.  Check if there are any consumable attachments.
4.  If so, instruct paperless to consume the attachments and optionally
    use the metadata provided in the rule for the new document.
5.  If documents were consumed from a mail, the rule action is performed
    on that mail.

Paperless will completely ignore mails that do not match your filters. It will also
only perform the action on mails that it has consumed documents from.

The actions all ensure that the same mail is not consumed twice by different means.
These are as follows:

*   **Delete:** Immediately deletes mail that paperless has consumed documents from.
    Use with caution.
*   **Mark as read:** Mark consumed mail as read. Paperless will not consume documents
    from already read mails. If you read a mail before paperless sees it, it will be
    ignored.
*   **Flag:** Sets the 'important' flag on mails with consumed documents. Paperless
    will not consume flagged mails.
*   **Move to folder:** Moves consumed mails out of the way so that paperless wont
    consume them again.

.. caution::

    The mail consumer will perform these actions on all mails it has consumed
    documents from. Keep in mind that the actual consumption process may fail
    for some reason, leaving you with missing documents in paperless.

.. note::

    With the correct set of rules, you can completely automate your email documents.
    Create rules for every correspondent you receive digital documents from and
    paperless will read them automatically. The default acion "mark as read" is
    pretty tame and will not cause any damage or data loss whatsoever.

    You can also setup a special folder in your mail account for paperless and use
    your favorite mail client to move to be consumed mails into that folder
    automatically or manually and tell paperless to move them to yet another folder
    after consumption. It's up to you.

.. note::

    Paperless will process the rules in the order defined in the admin page.

    You can define catch-all rules and have them executed last to consume
    any documents not matched by previous rules. Such a rule may assign an "Unknown
    mail document" tag to consumed documents so you can inspect them further.

Paperless is set up to check your mails every 10 minutes. This can be configured on the
'Scheduled tasks' page in the admin.


REST API
========

You can also submit a document using the REST API, see :ref:`api-file_uploads` for details.


.. _usage-recommended_workflow:

The recommended workflow
########################

Once you have familiarized yourself with paperless and are ready to use it
for all your documents, the recommended workflow for managing your documents
is as follows. This workflow also takes into account that some documents
have to be kept in physical form, but still ensures that you get all the
advantages for these documents as well.

The following diagram shows how easy it is to manage your documents.

.. image:: _static/recommended_workflow.png

Preparations in paperless
=========================

* Create an inbox tag that gets assigned to all new documents.
* Create a TODO tag.

Processing of the physical documents
====================================

Keep a physical inbox. Whenever you receive a document that you need to
archive, put it into your inbox. Regulary, do the following for all documents
in your inbox:

1.  For each document, decide if you need to keep the document in physical
    form. This applies to certain important documents, such as contracts and
    certificates.
2.  If you need to keep the document, write a running number on the document
    before scanning, starting at one and counting upwards. This is the archive
    serial number, or ASN in short.
3.  Scan the document.
4.  If the document has an ASN assigned, store it in a *single* binder, sorted
    by ASN. Don't order this binder in any other way.
5.  If the document has no ASN, throw it away. Yay!

Over time, you will notice that your physical binder will fill up. If it is
full, label the binder with the range of ASNs in this binder (i.e., "Documents
1 to 343"), store the binder in your cellar or elsewhere, and start a new
binder.

The idea behind this process is that you will never have to use the physical
binders to find a document. If you need a specific physical document, you
may find this document by:

1.  Searching in paperless for the document.
2.  Identify the ASN of the document, since it appears on the scan.
3.  Grab the relevant document binder and get the document. This is easy since
    they are sorted by ASN.

Processing of documents in paperless
====================================

Once you have scanned in a document, proceed in paperless as follows.

1.  If the document has an ASN, assign the ASN to the document.
2.  Assign a correspondent to the document (i.e., your employer, bank, etc)
    This isnt strictly necessary but helps in finding a document when you need
    it.
3.  Assign a document type (i.e., invoice, bank statement, etc) to the document
    This isnt strictly necessary but helps in finding a document when you need
    it.
4.  Assign a proper title to the document (the name of an item you bought, the
    subject of the letter, etc)
5.  Check that the date of the document is corrent. Paperless tries to read
    the date from the content of the document, but this fails sometimes if the
    OCR is bad or multiple dates appear on the document.
6.  Remove inbox tags from the documents.


Task management
===============

Some documents require attention and require you to act on the document. You
may take two different approaches to handle these documents based on how
regularly you intent to use paperless and scan documents.

* If you scan and process your documents in paperless regularly, assign a
  TODO tag to all scanned documents that you need to process. Create a saved
  view on the dashboard that shows all documents with this tag.
* If you do not scan documents regularly and use paperless solely for archiving,
  create a physical todo box next to your physical inbox and put documents you
  need to process in the TODO box. When you performed the task associated with
  the document, move it to the inbox.
