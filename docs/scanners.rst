
.. _scanners:

***********************
Scanner recommendations
***********************

As Paperless operates by watching a folder for new files, doesn't care what
scanner you use, but sometimes finding a scanner that will write to an FTP,
NFS, or SMB server can be difficult.  This page is here to help you find one
that works right for you based on recommendations from other Paperless users.

Physical scanners
=================

+---------+----------------+-----+-----+-----+------+----------+----------------+
| Brand   | Model          | Supports                          | Recommended By |
+---------+----------------+-----+-----+-----+------+----------+----------------+
|         |                | FTP | NFS | SMB | SMTP | API [1]_ |                |
+=========+================+=====+=====+=====+======+==========+================+
| Brother | `ADS-1700W`_   | yes | no  | yes | yes  |          |`holzhannes`_   |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Brother | `ADS-1600W`_   | yes | no  | yes | yes  |          |`holzhannes`_   |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Brother | `ADS-1500W`_   | yes | no  | yes | yes  |          |`danielquinn`_  |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Brother | `ADS-1100W`_   | yes | no  | no  | no   |          |`ytzelf`_       |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Brother | `MFC-J6930DW`_ | yes |     |     |      |          |`ayounggun`_    |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Brother | `MFC-L5850DW`_ | yes |     |     | yes  |          |`holzhannes`_   |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Brother | `MFC-J5910DW`_ | yes |     |     |      |          |`bmsleight`_    |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Brother | `MFC-9142CDN`_ | yes |     | yes |      |          |`REOLDEV`_      |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Fujitsu | `ix500`_       | yes |     | yes |      |          |`eonist`_       |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Epson   | `WF-7710DWF`_  | yes |     | yes |      |          |`Skylinar`_     |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Fujitsu | `S1300i`_      | yes |     | yes |      |          |`jonaswinkler`_ |
+---------+----------------+-----+-----+-----+------+----------+----------------+
| Doxie   | `Q2`_          | no  | no  | no  | no   | yes      |`Unkn0wnCat`_   |
+---------+----------------+-----+-----+-----+------+----------+----------------+

.. _MFC-L5850DW: https://www.brother-usa.com/products/mfcl5850dw
.. _ADS-1700W: https://www.brother-usa.com/products/ads1700w
.. _ADS-1600W: https://www.brother-usa.com/products/ads1600w
.. _ADS-1500W: https://www.brother.ca/en/p/ads1500w
.. _ADS-1100W: https://support.brother.com/g/b/downloadtop.aspx?c=fr&lang=fr&prod=ads1100w_eu_as_cn
.. _MFC-J6930DW: https://www.brother.ca/en/p/MFCJ6930DW
.. _MFC-J5910DW: https://www.brother.co.uk/printers/inkjet-printers/mfcj5910dw
.. _MFC-9142CDN: https://www.brother.co.uk/printers/laser-printers/mfc9140cdn
.. _ix500: http://www.fujitsu.com/us/products/computing/peripheral/scanners/scansnap/ix500/
.. _WF-7710DWF: https://www.epson.de/en/products/printers/inkjet-printers/for-home/workforce-wf-7710dwf
.. _S1300i: https://www.fujitsu.com/global/products/computing/peripheral/scanners/soho/s1300i/
.. _Q2: https://www.getdoxie.com/product/doxie-q/


.. _danielquinn: https://github.com/danielquinn
.. _ayounggun: https://github.com/ayounggun
.. _bmsleight: https://github.com/bmsleight
.. _eonist: https://github.com/eonist
.. _REOLDEV: https://github.com/REOLDEV
.. _Skylinar: https://github.com/Skylinar
.. _jonaswinkler: https://github.com/jonaswinkler
.. _holzhannes: https://github.com/holzhannes
.. _ytzelf: https://github.com/ytzelf
.. _Unkn0wnCat: https://github.com/Unkn0wnCat

.. [1] Scanners with API Integration allow to push scanned documents directly to :ref:`Paperless API <api-file_uploads>`, sometimes referred to as Webhook or Document POST.

Mobile phone software
=====================

You can use your phone to "scan" documents. The regular camera app will work, but may have too low contrast for OCR to work well. Apps specifically for scanning are recommended.

+-------------------+----------------+-----+-----+-----+-------+--------+------------------+
| Name              | OS             | Supports                         | Recommended By   |
+-------------------+----------------+-----+-----+-----+-------+--------+------------------+
|                   |                | FTP | NFS | SMB | Email | WebDav |                  |
+===================+================+=====+=====+=====+=======+========+==================+
| `Office Lens`_    | Android        | ?   | ?   | ?   | ?     | ?      | `jonaswinkler`_  |
+-------------------+----------------+-----+-----+-----+-------+--------+------------------+
| `Genius Scan`_    | Android        | yes | no  | yes | yes   | yes    | `hannahswain`_   |
+-------------------+----------------+-----+-----+-----+-------+--------+------------------+
| `OpenScan`_       | Android        | no  | no  | no  | no    | no     | `benjaminfrank`_ |
+-------------------+----------------+-----+-----+-----+-------+--------+------------------+
| `Quick Scan`_     | iOS            | no  | no  | no  | no    | no     | `holzhannes`_    |
+-------------------+----------------+-----+-----+-----+-------+--------+------------------+

On Android, you can use these applications in combination with one of the :ref:`Paperless-ng compatible apps <usage-mobile_upload>` to "Share" the documents produced by these scanner apps with paperless. On iOS, you can share the scanned documents via iOS-Sharing to other mail, WebDav or FTP apps.

.. _Office Lens: https://play.google.com/store/apps/details?id=com.microsoft.office.officelens
.. _Genius Scan: https://play.google.com/store/apps/details?id=com.thegrizzlylabs.geniusscan.free
.. _Quick Scan: https://apps.apple.com/us/app/quickscan-scanner-text-ocr/id1513790291
.. _OpenScan: https://github.com/Ethereal-Developers-Inc/OpenScan

.. _hannahswain: https://github.com/hannahswain
.. _benjaminfrank: https://github.com/benjaminfrank
