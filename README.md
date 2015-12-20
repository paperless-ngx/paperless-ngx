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

Here's how it works:

1. Buy a document scanner like [this one](http://welcome.brother.com/sg-en/products-services/scanners/ads-1100w.html).
2. Set it up to "scan to FTP".  This means you can use it without being
   connected to a running computer. It will just scan the document and save it
   as a PDF on a server in your house.
3. Setup a cronjob on that server to use *paperless* to OCR the PDF and index
   it into a local database.
4. Use the web frontend to sift through the database and find what you want.
5. Download the PDF you need/want via the web interface and do whatever you
   like with it.  You can even print it and send it as if it's the original.
   In most cases, no one will care or notice.
