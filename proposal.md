# Proposal for handling arbitrary file types in Paperless-ngx

I would like to propose changes and extensions for handling arbitrary file types in Paperless-ngx. This includes suggestions for a new parser handling and changes to the handling of filenames and file extensions.

I would be happy to implement these changes. Before doing a corresponding pull request, however, I would first like to put the proposals up for discussion and at the same time signal that I am working on such a solution.

## Background

In some discussions, the wish has already been expressed to be able to archive arbitrary file types in Paperless-ngx, e.g:

- Support for arbitrary binary files?
  https://github.com/paperless-ngx/paperless-ngx/discussions/805

- [Feature Request] RAW-Handling of all sorts of fileextension
  https://github.com/paperless-ngx/paperless-ngx/discussions/5727

- [Feature Request] Add support for DICOM files (medical images)
  https://github.com/paperless-ngx/paperless-ngx/discussions/5066

Users want to store files of their tax software, medical images or CAD drawings in Paperless-ngx. Hereby archiving these documents with the standard options that Paperless-ngx offers for searching documents (standard metadata, tagging) is sufficient for them. A preview or content extraction is not absolutely necessary. Such files can have a wide variety of mime types and file extensions.

There is also the use case that you want to process files of the same mime type but with different file extensions in a differentiated way. For example, in addition to the supplied parser for TXT files, you may want to define a parser that offers a specifically formatted preview for YAML files.

Another use case are files of different tax programs having the mime type application/octet-stream, which are to be processed differently in order to obtain a preview of the data.

Another example would be the archiving certificates with file extension ".pfx", which also have mime type application/octet-stream.

Paperless-ngx does offer the option of defining your own parsers. However, at the moment it is mandatory to define which mime types they process and to specify for each affected mime type which (standard) file extension should be used when a file of this mime type is saved or downloaded.

## Changes to the parser handling

I would therefore like to suggest changing the parser handling as follows:

Each parser defines in its consumer declaration a dictionary "file*types" with \_mime-type* as key and a _list of file extensions_ as value. Here, _mime-type_ may also be the empty string. _List of file extensions_ may also be the empty list.

For downward compatibility, the existing entry "mime_types" is not redefined here, but the new entry "file_types" is used.

The possible entries in the "file_types" dictionary are interpreted as follows:

1. Use Case: a parser that is used for all files whose mime-type corresponds to the specified "mime-type" and which have one of the specified file extensions ".a" or ".b".

   ```
   "file_types": {
       "mime-type": [".a", ".b"],
   }
   ```

2. Use Case: a parser that is used for all files that have one of the specified file extensions ".a" or ".b" (regardless of which mime type they have).

   ```
   "file_types": {
       "": [".a", ".b"],
   }
   ```

   This can also be used, for example, to cover the case that PDF files with the file extension ".pdf" have a different mime type due to deviations from the standard. The special handling from commit 5e687d9, which currently takes place in the ConsumerPlugin, could thus be encapsulated in the PDF parser, see:

   - Feature: auto-clean some invalid pdfs

     https://github.com/paperless-ngx/paperless-ngx/discussions/7651

   - PAPERLESS_APPS to extend the default PDF parser to handle application/octet-stream

     https://github.com/paperless-ngx/paperless-ngx/discussions/6563

3. Use Case: a parser that is used for all files whose mime-type corresponds to the specified "mime-type" (regardless of what file extension they have).

   ```
   "file_types": {
       "mime-type": [],
   }
   ```

   Please see also section [Change regarding file extension](#change-regarding-file-extension) below.

4. Use Case: a parser that is used for all files (regardless of their mime-type and file extension).

   ```
   "file_types": {}
   ```

   Note: According to the systematic defined above, the definition for this case would actually be

   ```
   "file_types": {
       "": [],
   }
   ```

   However, as it makes no sense to declare further file types for a parser with this file type entry, it is sufficient to assign the empty dictionary to "file_types".

As with the actual parser definition, each parser is assigned a weight.

The best parser for a file is then determined as follows:

- Get all parsers _A_ which match the mime type or file extension of the file (including use case 4)

- If _A_ is not empty, the best parser is parser _a_ from _A_ with the highest weight.

  - If there is more than one parser _a_ get the first one in the list (no further sorting) and throw a warning

  - otherwise return the only parser

- else throw an exception, that no parser was found for the file

The consumer declaration of a parser must contain either a "mime_types" or a "file_types" definition.

Example definitions:

```
# Example for use case 1

def myparser_consumer_declaration(sender, **kwargs):
    return {
        "parser": PKCS12CertParser,
        "weight": 0,
        "file_types": {
            "application/octet-stream": [".pfx",".p12"]
        }
    }

# Another example for use case 1

def myparser_consumer_declaration(sender, **kwargs):
    return {
        "parser": YamlParser,
        "weight": 0,
        "file_types": {
            "text/plain": [".yaml"]
        }
    }

# Example for use case 2

def myparser_consumer_declaration(sender, **kwargs):
    return {
        "parser": PDFParser,
        "weight": 0,
        "file_types": {
            "": [".pdf"],
        }
    }

# Another example for use case 2

def myparser_consumer_declaration(sender, **kwargs):
    return {
        "parser": DefaultParserForFilesWithoutExtensionOnly,
        "weight": 0,
        "mime_types": {
            "": [""],
        }
    }

# Example for use case 3

def myparser_consumer_declaration(sender, **kwargs):
    return {
        "parser": PictureParser
        "weight": 0,
        "file_types": {
            "image/png": [],
            "image/jpeg": []
        }
    }

# Example for use case 4

def myparser_consumer_declaration(sender, **kwargs):
    return {
        "parser": DefaultParser,
        "weight": 0,
        "file_types": {
        }
    }

```

## Standard parser

Use case 4 allows the declaration of a standard parser, which always takes effect if no other suitable parser is found.

For this purpose, I suggest implementing the following standard parser, see the example declaration for use case 4 above

- "file_types" is the empty dictionary
- "weight" is 0
- The parser does not create an archive version of the file
- The parser does not generate a preview image. Alternative: The parser generates a preview image with e.g. only the mime type designation to prevent confusion on the part of the user because he does not see a preview image.

- The content attribute
  - remains empty or
  - is filled with the interpretation of the file as an ASCII-encoded text file. With this variant, searching within documents could be used similar to a "grep" on binary files.

## Changes regarding the file extension

I ask myself why it is currently necessary to specify a standard file extension when defining parsers. From my point of view - especially for the standard parser proposed here - no change to the original file extension is desired when saving and downloading.

In the use cases mentioned at the beginning (CAD, tax software, DCOM, YAML files), changing the file extension is even a hindrance, as changing the file extension, e.g. to ".bin" (as it is currently the case with the mime type application/octect-stream) or ".txt" (as with the mime type text/plain), prevents the file from being used with the original application or the file extension would have to be corrected manually before using the file with the original application.

See also: Allow download without formatted filename in document view https://github.com/paperless-ngx/paperless-ngx/discussions/4949

I would therefore suggest that the file extension of the original file is used when saving. The same applies when downloading the (original) file.

If a general change is not desired, the use of the original file extension could be switched on by activating an option PAPERLESS_FILENAME_USE_ORIGINAL_EXTENSION, for example.

If I have overlooked something regarding the default file extension per mime type that is actually mandatory when defining a parser, please let me know.

## Changes regarding the file name

Currently, when downloading a document as a single file, the file name is created according to the pattern

`{created}[ {correspondent}][ {title}][_{counter}][{suffix}]{self.file_type}`

where `[]` indicates optional components here.

In my opinion, the original file name - including the original file extension - should be used for single downloads, especially when using the standard parser, see again: Allow download without formatted filename in document view https://github.com/paperless-ngx/paperless-ngx/discussions/4949

As with the file extension, the same applies here: If no general change is desired, the original file name including the original file extension could be used by activating a configuration variable PAPERLESS_FILENAME_USE_ORIGINAL_NAME.

An alternative would be to make the file name for the single file download configurable in the same way as with the bulk download (see variable PAPERLESS_FILENAME_FORMAT). In this case, however, a new variable `{original_name}` would have to be available in addition to `{original_suffix}`.

## Custom Parser Documentation

Finally, I would like to suggest adding the following to the documentation at

https://docs.paperless-ngx.com/development/#making-custom-parsers:

_The custom parser must be added to the variable PAPERLESS_APPS in paperless.conf._

# Pure nonsense?

I look forward to feedback on the proposal ;-)
