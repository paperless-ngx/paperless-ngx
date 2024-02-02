<div class="grid-left" markdown>
![image](assets/logo_full_black.svg#only-light){.index-logo}
![image](assets/logo_full_white.svg#only-dark){.index-logo}

**Paperless-ngx** is a _community-supported_ open-source document management system that transforms your
physical documents into a searchable online archive so you can keep, well, _less paper_.

[Get started](setup.md){ .md-button .md-button--primary .index-callout }
[Demo](https://demo.paperless-ngx.com){ .md-button .md-button--secondary target=\_blank }

<div style="display: flex; justify-content: end; margin-top: -1.5rem;">
  <a href="https://m.do.co/c/8d70b916d462" target="_blank">
    <img src="https://opensource.nyc3.cdn.digitaloceanspaces.com/attribution/assets/PoweredByDO/DO_Powered_by_Badge_white.svg#only-dark" class="no-lightbox" width="150px">
    <img src="https://opensource.nyc3.cdn.digitaloceanspaces.com/attribution/assets/PoweredByDO/DO_Powered_by_Badge_black.svg#only-light" class="no-lightbox" width="150px">
  </a>
</div>

</div>
<div class="grid-right" markdown>
![image](assets/screenshots/documents-smallcards.png#only-light){.index-screenshot}
![image](assets/screenshots/documents-smallcards-dark.png#only-dark){.index-screenshot}
</div>
<div class="clear"></div>

## Features

-   **Organize and index** your scanned documents with tags, correspondents, types, and more.
-   _Your_ data is stored locally on _your_ server and is never transmitted or shared in any way.
-   Performs **OCR** on your documents, adding searchable and selectable text, even to documents scanned with only images.
-   Utilizes the open-source Tesseract engine to recognize more than 100 languages.
-   Documents are saved as PDF/A format which is designed for long term storage, alongside the unaltered originals.
-   Uses machine-learning to automatically add tags, correspondents and document types to your documents.
-   Supports PDF documents, images, plain text files, Office documents (Word, Excel, Powerpoint, and LibreOffice equivalents)[^1] and more.
-   Paperless stores your documents plain on disk. Filenames and folders are managed by paperless and their format can be configured freely with different configurations assigned to different documents.
-   **Beautiful, modern web application** that features:
    -   Customizable dashboard with statistics.
    -   Filtering by tags, correspondents, types, and more.
    -   Bulk editing of tags, correspondents, types and more.
    -   Drag-and-drop uploading of documents throughout the app.
    -   Customizable views can be saved and displayed on the dashboard and / or sidebar.
    -   Support for custom fields of various data types.
    -   Shareable public links with optional expiration.
-   **Full text search** helps you find what you need:
    -   Auto completion suggests relevant words from your documents.
    -   Results are sorted by relevance to your search query.
    -   Highlighting shows you which parts of the document matched the query.
    -   Searching for similar documents ("More like this")
-   **Email processing**[^1]: import documents from your email accounts:
    -   Configure multiple accounts and rules for each account.
    -   After processing, paperless can perform actions on the messages such as marking as read, deleting and more.
-   A built-in robust **multi-user permissions** system that supports 'global' permissions as well as per document or object.
-   A powerful workflow system that gives you even more control.
-   **Optimized** for multi core systems: Paperless-ngx consumes multiple documents in parallel.
-   The integrated sanity checker makes sure that your document archive is in good health.

[^1]: Office document and email consumption support is optional and provided by Apache Tika (see [configuration](https://docs.paperless-ngx.com/configuration/#tika))

## Paperless, a history

Paperless-ngx is the official successor to the original [Paperless](https://github.com/the-paperless-project/paperless) & [Paperless-ng](https://github.com/jonaswinkler/paperless-ng) projects and is designed to distribute the responsibility of advancing and supporting the project among a team of people. [Consider joining us!](https://github.com/paperless-ngx/paperless-ngx#community-support)

Further discussion of the transition between these projects can be found at
[ng#1599](https://github.com/jonaswinkler/paperless-ng/issues/1599) and [ng#1632](https://github.com/jonaswinkler/paperless-ng/issues/1632).

## Screenshots

Paperless-ngx aims to be as nice to use as it is useful. Check out some screenshots below.

<div class="grid-flipped-left" markdown>
  ![image](assets/screenshots/dashboard.png)
</div>
<div class="grid-flipped-right" markdown>
  The dashboard shows saved views which can be sorted. Documents can be uploaded with the button or dropped anywhere in the application.
</div>
<div class="clear"></div>

The document list provides three different styles to browse your documents.

![image](assets/screenshots/documents-table.png){: style="width:32%"}
![image](assets/screenshots/documents-smallcards.png){: style="width:32%"}
![image](assets/screenshots/documents-largecards.png){: style="width:32%"}

<div class="clear"></div>

<div class="grid-left" markdown>
  Use the 'slim' sidebar to focus on your docs and minimize the UI.
</div>
<div class="grid-right" markdown>
  ![image](assets/screenshots/documents-smallcards-slimsidebar.png)
</div>
<div class="clear"></div>

Of course, Paperless-ngx also supports dark mode:

![image](assets/screenshots/documents-smallcards-dark.png)

<div class="clear"></div>

<div class="grid-left" markdown>
  Quickly find documents with extensive filtering mechanisms.
</div>
<div class="grid-right" markdown>
  ![image](assets/screenshots/documents-filter.png)
</div>
<div class="clear"></div>
<div class="grid-left" markdown>
  And perform bulk edit operations to set tags, correspondents, etc. as well as permissions.
</div>
<div class="grid-right" markdown>
  ![image](assets/screenshots/bulk-edit.png)
</div>
<div class="clear"></div>

Side-by-side editing of documents.

![image](assets/screenshots/editing.png)

<div class="grid-left" markdown>
  Support for custom fields.

![image](assets/screenshots/custom_field1.png)

</div>
<div class="grid-right" markdown>
  ![image](assets/screenshots/custom_field2.png)
</div>
<div class="clear"></div>

<div class="grid-left" markdown>
  A robust permissions system with support for 'global' and document / object permissions.

![image](assets/screenshots/permissions_global.png)

</div>
<div class="grid-right" markdown>
  ![image](assets/screenshots/permissions_document.png)
</div>
<div class="clear"></div>

<div class="grid-left" markdown>
  Searching provides auto complete and highlights the results.

![image](assets/screenshots/search-preview.png)

</div>
<div class="grid-right" markdown>
  ![image](assets/screenshots/search-results.png)
</div>
<div class="clear"></div>

Tag, correspondent, document type and storage path editing.

![image](assets/screenshots/new-tag.png){: style="width:21%; float: left"}
![image](assets/screenshots/new-correspondent.png){: style="width:21%; margin-left: 4%; float: left"}
![image](assets/screenshots/new-document_type.png){: style="width:21%; margin-left: 4%; float: left"}
![image](assets/screenshots/new-storage_path.png){: style="width:21%; margin-left: 4%; float: left"}

<div class="clear"></div>

<div class="grid-half-left" markdown>
  Mail rules support various filters and actions for incoming e-mails.

![image](assets/screenshots/mail-rules-edited.png)

</div>
<div class="grid-half-right" markdown>
  Workflows provide finer control over the document pipeline and trigger actions.

![image](assets/screenshots/workflow.png)

</div>
<div class="clear"></div>

<div class="clear"></div>

Mobile devices are supported.

![image](assets/screenshots/mobile1.png){: style="width:32%"}
![image](assets/screenshots/mobile2.png){: style="width:32%"}
![image](assets/screenshots/mobile3.png){: style="width:32%"}

## Support

Community support is available via [GitHub Discussions](https://github.com/paperless-ngx/paperless-ngx/discussions/) and [the Matrix chat room](https://matrix.to/#/#paperless:matrix.org).

### Feature Requests

Feature requests can be submitted via [GitHub Discussions](https://github.com/paperless-ngx/paperless-ngx/discussions/categories/feature-requests) where you can search for existing ideas, add your own and vote for the ones you care about.

### Bugs

For bugs please [open an issue](https://github.com/paperless-ngx/paperless-ngx/issues) or [start a discussion](https://github.com/paperless-ngx/paperless-ngx/discussions/categories/support) if you have questions.

## Contributing

People interested in continuing the work on paperless-ngx are encouraged to reach out on [GitHub](https://github.com/paperless-ngx/paperless-ngx) or [the Matrix chat room](https://matrix.to/#/#paperless:matrix.org). If you would like to contribute to the project on an ongoing basis there are multiple teams (frontend, ci/cd, etc) that could use your help so please reach out!

### Translation

Paperless-ngx is available in many languages that are coordinated on [Crowdin](https://crwd.in/paperless-ngx). If you want to help out by translating paperless-ngx into your language, please head over to the [Paperless-ngx project at Crowdin](https://crwd.in/paperless-ngx), and thank you!

## Scanners & Software

Paperless-ngx is compatible with many different scanners and scanning tools. A user-maintained list of scanners and other software is available on [the wiki](https://github.com/paperless-ngx/paperless-ngx/wiki/Scanner-&-Software-Recommendations).
