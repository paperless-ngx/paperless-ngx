---
title: FAQs
---

# Frequently Asked Questions

## _What's the general plan for Paperless-ngx?_

**A:** While Paperless-ngx is already considered largely
"feature-complete", it is a community-driven project and development
will be guided in this way. New features can be submitted via
[GitHub discussions](https://github.com/paperless-ngx/paperless-ngx/discussions)
and "up-voted" by the community, but this is not a
guarantee that the feature will be implemented. This project will always be
open to collaboration in the form of PRs, ideas etc.

## _I'm using docker. Where are my documents?_

**A:** By default, your documents are stored inside the docker volume
`paperless_media`. Docker manages this volume automatically for you. It
is a persistent storage and will persist as long as you don't
explicitly delete it. The actual location depends on your host operating
system. On Linux, chances are high that this location is

```
/var/lib/docker/volumes/paperless_media/_data
```

!!! warning

    Do not mess with this folder. Don't change permissions and don't move
    files around manually. This folder is meant to be entirely managed by
    docker and paperless.

!!! note

    Files consumed from the consumption directory are re-created inside
    this media directory and are removed from the consumption directory
    itself.

## Let's say I want to switch tools in a year. Can I easily move to other systems?

**A:** Your documents are stored as plain files inside the media folder.
You can always drag those files out of that folder to use them
elsewhere. Here are a couple notes about that.

- Paperless-ngx never modifies your original documents. It keeps
  checksums of all documents and uses a scheduled sanity checker to
  check that they remain the same.
- By default, paperless uses the internal ID of each document as its
  filename. This might not be very convenient for export. However, you
  can adjust the way files are stored in paperless by
  [configuring the filename format](advanced_usage.md#file-name-handling).
- [The exporter](administration.md#exporter) is
  another easy way to get your files out of paperless with reasonable
  file names.

## _What file types does paperless-ngx support?_

**A:** Currently, the following files are supported:

- PDF documents, PNG images, JPEG images, TIFF images, GIF images and
  WebP images are processed with OCR and converted into PDF documents.
- Plain text documents are supported as well and are added verbatim to
  paperless.
- With the optional Tika integration enabled (see [Tika configuration](https://docs.paperless-ngx.com/configuration#tika)),
  Paperless also supports various Office documents (.docx, .doc, odt,
  .ppt, .pptx, .odp, .xls, .xlsx, .ods).

Paperless-ngx determines the type of a file by inspecting its content
rather than its file extensions. However, files processed via the
consumption directory will be rejected if they have a file extension that
is not supported by any of the available parsers.

## _Are duplicate documents rejected?_

**A:** Not by default. As of v3, a file whose contents match an existing document is still
consumed, and the duplicate is flagged in the UI — open the document and check the
**Duplicates** tab to review documents that share the same content. If you prefer the old
behavior of rejecting duplicates during consumption, set
[`PAPERLESS_CONSUMER_DELETE_DUPLICATES`](configuration.md#PAPERLESS_CONSUMER_DELETE_DUPLICATES)
to `true`.

## _Will paperless-ngx run on Raspberry Pi?_

**A:** The short answer is yes. I've tested it on a Raspberry Pi 3 B.
The long answer is that certain parts of Paperless will run very slow,
such as the OCR. On Raspberry Pi, try to OCR documents before feeding
them into paperless so that paperless can reuse the text. The web
interface is a lot snappier, since it runs in your browser and paperless
has to do much less work to serve the data.

!!! note

    You can adjust some of the settings so that paperless uses less
    processing power. See [setup](setup.md#less-powerful-devices) for details.

## _How do I install paperless-ngx on Raspberry Pi?_

**A:** Docker images are available for arm64 hardware, so just
follow the [Docker Compose instructions](https://docs.paperless-ngx.com/setup/#installation). Apart from more required disk
space compared to a bare metal installation, docker comes with close to
zero overhead, even on Raspberry Pi.

If you decide to go with the bare metal route, be aware that some of
the python requirements do not have precompiled packages for ARM /
ARM64. Installation of these will require additional development
libraries and compilation will take a long time.

!!! note

    For ARMv7 (32-bit) systems, paperless may still function, but it could require
    modifications to the Dockerfile (if using Docker) or additional
    tools for installing bare metal.  It is suggested to upgrade to arm64
    instead.

## _How do I run this on Unraid?_

**A:** Paperless-ngx is available as [community
app](https://unraid.net/community/apps?q=paperless-ngx) in Unraid. [Uli
Fahrer](https://github.com/Tooa) created a container template for that.

## _How do I run this on my toaster?_

**A:** I honestly don't know! As for all other devices that might be
able to run paperless, you're a bit on your own. If you can't run the
docker image, the documentation has instructions for bare metal
installs.

## _Does Paperless-ngx use AI, and is my data private?_

**A:** Paperless-ngx includes optional AI features — LLM-based suggestions, document chat,
and similar-document retrieval — that are **disabled by default**. They only run when you
enable them and configure an LLM backend. The built-in tag/correspondent suggestions use a
local, non-LLM machine-learning model and do not send your data anywhere. If you enable the
LLM features, document content is sent to whichever backend you configure — this can be a
fully local backend (e.g. Ollama) or a remote provider. See
[AI features](advanced_usage.md#ai-features) for details.

## _Which message broker should I use_?

Paperless-ngx talks to a Redis-compatible message broker, so any broker that
implements the Redis protocol will work. The bundled Docker Compose files
default to [Valkey](https://valkey.io/), the open-source fork created after
Redis' licensing change, but Redis itself and other wire-compatible brokers
(such as Microsoft's Garnet) are equally fine.

Existing installs can switch broker implementations in place: point
[`PAPERLESS_REDIS`](configuration.md#PAPERLESS_REDIS) at the new instance and
reuse the same data volume.
