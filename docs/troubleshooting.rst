.. _troubleshooting:

Troubleshooting
===============

.. _troubleshooting_ocr_language_files_missing:

Consumer warns ``OCR for XX failed``
------------------------------------

If you find the OCR accuracy to be too low, and/or the document consumer warns that ``OCR for
XX failed, but we're going to stick with what we've got since FORGIVING_OCR is enabled``, then you
might need to install the `Tesseract language files
<http://packages.ubuntu.com/search?keywords=tesseract-ocr>`_ marching your documents languages.

As an example, if you are running Paperless from the Vagrant setup provided (or from any Ubuntu or Debian
box), and your documents are written in Spanish you may need to run::

    apt-get install -y tesseract-ocr-spa
