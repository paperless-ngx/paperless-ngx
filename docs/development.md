# Development

This section describes the steps you need to take to start development
on Paperless-ngx.

Check out the source from GitHub. The repository is organized in the
following way:

- `main` always represents the latest release and will only see
  changes when a new release is made.
- `dev` contains the code that will be in the next release.
- `feature-X` contains bigger changes that will be in some release, but
  not necessarily the next one.

When making functional changes to Paperless-ngx, _always_ make your changes
on the `dev` branch.

Apart from that, the folder structure is as follows:

- `docs/` - Documentation.
- `src-ui/` - Code of the front end.
- `src/` - Code of the back end.
- `scripts/` - Various scripts that help with different parts of
  development.
- `docker/` - Files required to build the docker image.

## Contributing to Paperless-ngx

Maybe you've been using Paperless-ngx for a while and want to add a feature
or two, or maybe you've come across a bug that you have some ideas how
to solve. The beauty of open source software is that you can see what's
wrong and help to get it fixed for everyone!

Before contributing please review our [code of
conduct](https://github.com/paperless-ngx/paperless-ngx/blob/main/CODE_OF_CONDUCT.md)
and other important information in the [contributing
guidelines](https://github.com/paperless-ngx/paperless-ngx/blob/main/CONTRIBUTING.md).

## Code formatting with pre-commit hooks

To ensure a consistent style and formatting across the project source,
the project utilizes Git [`pre-commit`](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)
hooks to perform some formatting and linting before a commit is allowed.
That way, everyone uses the same style and some common issues can be caught
early on.

Once installed, hooks will run when you commit. If the formatting isn't
quite right or a linter catches something, the commit will be rejected.
You'll need to look at the output and fix the issue. Some hooks, such
as the Python linting and formatting tool `ruff`, will format failing
files, so all you need to do is `git add` those files again
and retry your commit.

## General setup

After you forked and cloned the code from GitHub you need to perform a
first-time setup.

!!! note

      Every command is executed directly from the root folder of the project unless specified otherwise.

1.  Install prerequisites + [uv](https://github.com/astral-sh/uv) as mentioned in
    [Bare metal route](setup.md#bare_metal).

2.  Copy `paperless.conf.example` to `paperless.conf` and enable debug
    mode within the file via `PAPERLESS_DEBUG=true`.

3.  Create `consume` and `media` directories:

    ```bash
    mkdir -p consume media
    ```

4.  Install the Python dependencies:

    ```bash
    uv sync --group dev
    ```

5.  Install pre-commit hooks:

    ```bash
    uv run prek install
    ```

6.  Apply migrations and create a superuser (also can be done via the web UI) for your development instance:

    ```bash
    # src/

    uv run manage.py migrate
    uv run manage.py createsuperuser
    ```

7.  You can now either ...
    - install Redis or

    - use the included `scripts/start_services.sh` to use Docker to fire
      up a Redis instance (and some other services such as Tika,
      Gotenberg and a database server) or

    - spin up a bare Redis container

      ```bash
      docker run -d -p 6379:6379 --restart unless-stopped redis:latest
      ```

8.  Continue with either back-end or front-end development – or both :-).

## Back end development

The back end is a [Django](https://www.djangoproject.com/) application.
[PyCharm](https://www.jetbrains.com/de-de/pycharm/) as well as [Visual Studio Code](https://code.visualstudio.com)
work well for development, but you can use whatever you want.

Configure the IDE to use the `src/`-folder as the base source folder.
Configure the following launch configurations in your IDE:

- `uv run manage.py runserver`
- `uv run manage.py document_consumer`
- `uv run celery --app paperless worker -l DEBUG` (or any other log level)

To start them all:

```bash
# src/

uv run manage.py runserver & \
  uv run manage.py document_consumer & \
  uv run celery --app paperless worker -l DEBUG
```

You might need the front end to test your back end code.
This assumes that you have AngularJS installed on your system.
Go to the [Front end development](#front-end-development) section for further details.
To build the front end once use this command:

```bash
# src-ui/

pnpm install
pnpm ng build --configuration production
```

### Testing

- Run `pytest` in the `src/` directory to execute all tests. This also
  generates a HTML coverage report. When running tests, `paperless.conf`
  is loaded as well. However, the tests rely on the default
  configuration. This is not ideal. But for now, make sure no settings
  except for DEBUG are overridden when testing.

!!! note

      The line length rule E501 is generally useful for getting multiple
      source files next to each other on the screen. However, in some
      cases, its just not possible to make some lines fit, especially
      complicated IF cases. Append `# noqa: E501` to disable this check
      for certain lines.

### Package Management

Paperless uses `uv` to manage packages and virtual environments for both development and production.
To accomplish some common tasks using `uv`, follow the shortcuts below:

To upgrade all locked packages to the latest allowed versions: `uv lock --upgrade`

To upgrade a single locked package: `uv lock --upgrade-package <package>`

To add a new package: `uv add <package>`

To add a new development package `uv add --dev <package>`

## Front end development

The front end is built using AngularJS. In order to get started, you need Node.js (version 24+) and
`pnpm`.

!!! note

    The following commands are all performed in the `src-ui`-directory. You will need a running back end (including an active session) to connect to the back end API. To spin it up refer to the commands under the section [above](#back-end-development).

1.  Install the Angular CLI. You might need sudo privileges to perform this command:

    ```bash
    pnpm install -g @angular/cli
    ```

2.  Make sure that it's on your path.

3.  Install all necessary modules:

    ```bash
    pnpm install
    ```

4.  You can launch a development server by running:

    ```bash
    pnpm ng serve
    ```

    This will automatically update whenever you save. However, in-place
    compilation might fail on syntax errors, in which case you need to
    restart it.

    By default, the development server is available on `http://localhost:4200/` and is configured to access the API at
    `http://localhost:8000/api/`, which is the default of the backend. If you enabled `DEBUG` on the back end, several security overrides for allowed hosts and CORS are in place so that the front end behaves exactly as in production.

### Testing and code style

The front end code (.ts, .html, .scss) use `prettier` for code
formatting via the Git `pre-commit` hooks which run automatically on
commit. See [above](#code-formatting-with-pre-commit-hooks) for installation instructions. You can also run this via the CLI with a
command such as

```bash
git ls-files -- '*.ts' | xargs uv run prek run prettier --files
```

Front end testing uses Jest and Playwright. Unit tests and e2e tests,
respectively, can be run non-interactively with:

```bash
pnpm ng test
pnpm playwright test
```

Playwright also includes a UI which can be run with:

```bash
pnpm playwright test --ui
```

### Building the frontend

In order to build the front end and serve it as part of Django, execute:

```bash
pnpm ng build --configuration production
```

This will build the front end and put it in a location from which the
Django server will serve it as static content. This way, you can verify
that authentication is working.

## Localization

Paperless-ngx is available in many different languages. Since Paperless-ngx
consists both of a Django application and an AngularJS front end, both
these parts have to be translated separately.

### Front end localization

- The AngularJS front end does localization according to the [Angular
  documentation](https://angular.io/guide/i18n).
- The source language of the project is "en_US".
- The source strings end up in the file `src-ui/messages.xlf`.
- The translated strings need to be placed in the
  `src-ui/src/locale/` folder.
- In order to extract added or changed strings from the source files,
  call `ng extract-i18n`.

Adding new languages requires adding the translated files in the
`src-ui/src/locale/` folder and adjusting a couple files.

1.  Adjust `src-ui/angular.json`:

    ```json
    "i18n": {
        "sourceLocale": "en-US",
        "locales": {
            "de": "src/locale/messages.de.xlf",
            "nl-NL": "src/locale/messages.nl_NL.xlf",
            "fr": "src/locale/messages.fr.xlf",
            "en-GB": "src/locale/messages.en_GB.xlf",
            "pt-BR": "src/locale/messages.pt_BR.xlf",
            "language-code": "language-file"
        }
    }
    ```

2.  Add the language to the `LANGUAGE_OPTIONS` array in
    `src-ui/src/app/services/settings.service.ts`:

    ```

    `dateInputFormat` is a special string that defines the behavior of
    the date input fields and absolutely needs to contain "dd", "mm"
    and "yyyy".

    ```

3.  Import and register the Angular data for this locale in
    `src-ui/src/app/app.module.ts`:

    ```typescript
    import localeDe from '@angular/common/locales/de'
    registerLocaleData(localeDe)
    ```

### Back end localization

A majority of the strings that appear in the back end appear only when
the admin is used. However, some of these are still shown on the front
end (such as error messages).

- The django application does localization according to the [Django
  documentation](https://docs.djangoproject.com/en/3.1/topics/i18n/translation/).
- The source language of the project is "en_US".
- Localization files end up in the folder `src/locale/`.
- In order to extract strings from the application, call
  `uv run manage.py makemessages -l en_US`. This is important after
  making changes to translatable strings.
- The message files need to be compiled for them to show up in the
  application. Call `uv run manage.py compilemessages` to do this.
  The generated files don't get committed into git, since these are
  derived artifacts. The build pipeline takes care of executing this
  command.

Adding new languages requires adding the translated files in the
`src/locale/`-folder and adjusting the file
`src/paperless/settings.py` to include the new language:

```python
LANGUAGES = [
    ("en-us", _("English (US)")),
    ("en-gb", _("English (GB)")),
    ("de", _("German")),
    ("nl-nl", _("Dutch")),
    ("fr", _("French")),
    ("pt-br", _("Portuguese (Brazil)")),
    # Add language here.
]
```

## Building the documentation

The documentation is built using Zensical, see their [documentation](https://zensical.org/docs/).
If you want to build the documentation locally, this is how you do it:

1.  Build the documentation

    ```bash
    $ uv run zensical build
    ```

    _alternatively..._

2.  Serve the documentation. This will spin up a
    copy of the documentation at http://127.0.0.1:8000
    that will automatically refresh every time you change
    something.

    ```bash
    $ uv run zensical serve
    ```

## Building the Docker image {#docker_build}

The docker image is primarily built by the GitHub actions workflow, but
it can be faster when developing to build and tag an image locally.

Make sure you have the `docker-buildx` package installed. Building the image works as with any image:

```
docker build --file Dockerfile --tag paperless:local .
```

## Extending Paperless-ngx

Paperless-ngx supports third-party document parsers via a Python entry point
plugin system. Plugins are distributed as ordinary Python packages and
discovered automatically at startup — no changes to the Paperless-ngx source
are required.

!!! warning "Third-party plugins are not officially supported"

    The Paperless-ngx maintainers do not provide support for third-party
    plugins. Issues that are caused by or require changes to a third-party
    plugin will be closed without further investigation. If you believe you
    have found a bug in Paperless-ngx itself (not in a plugin), please
    reproduce it with all third-party plugins removed before filing an issue.

### Making custom parsers

Paperless-ngx uses parsers to add documents. A parser is responsible for:

- Extracting plain-text content from the document
- Generating a thumbnail image
- _optional:_ Detecting the document's creation date
- _optional:_ Producing a searchable PDF archive copy

Custom parsers are distributed as ordinary Python packages and registered
via a [setuptools entry point](https://setuptools.pypa.io/en/latest/userguide/entry_point.html).
No changes to the Paperless-ngx source are required.

#### 1. Implementing the parser class

Your parser must satisfy the `ParserProtocol` structural interface defined in
`paperless.parsers`. The simplest approach is to write a plain class — no base
class is required, only the right attributes and methods.

**Class-level identity attributes**

The registry reads these before instantiating the parser, so they must be
plain class attributes (not instance attributes or properties):

```python
class MyCustomParser:
    name    = "My Format Parser"   # human-readable name shown in logs
    version = "1.0.0"              # semantic version string
    author  = "Acme Corp"          # author / organisation
    url     = "https://example.com/my-parser"  # docs or issue tracker
```

**Declaring supported MIME types**

Return a `dict` mapping MIME type strings to preferred file extensions
(including the leading dot). Paperless-ngx uses the extension when storing
archive copies and serving files for download.

```python
@classmethod
def supported_mime_types(cls) -> dict[str, str]:
    return {
        "application/x-my-format": ".myf",
        "application/x-my-format-alt": ".myf",
    }
```

**Scoring**

When more than one parser can handle a file, the registry calls `score()` on
each candidate and picks the one with the highest result and equal scores favor third-party parsers over built-ins. Return `None` to
decline handling a file even though the MIME type is listed as supported (for
example, when a required external service is not configured).

| Score  | Meaning                                                                           |
| ------ | --------------------------------------------------------------------------------- |
| `None` | Decline — do not handle this file                                                 |
| `10`   | Default priority used by all built-in parsers                                     |
| `20`   | Priority used by the remote OCR built-in parser, allowing it to replace Tesseract |
| `> 10` | Override a built-in parser for the same MIME type                                 |

```python
@classmethod
def score(
    cls,
    mime_type: str,
    filename: str,
    path: "Path | None" = None,
) -> int | None:
    # Inspect filename or file bytes here if needed.
    return 10
```

**Archive and rendition flags**

```python
@property
def can_produce_archive(self) -> bool:
    """True if parse() can produce a searchable PDF archive copy."""
    return True   # or False if your parser doesn't produce PDFs

@property
def requires_pdf_rendition(self) -> bool:
    """True if the original format cannot be displayed by a browser
    (e.g. DOCX, ODT) and the PDF output must always be kept."""
    return False
```

**Context manager — temp directory lifecycle**

Paperless-ngx always uses parsers as context managers. Create a temporary
working directory in `__enter__` (or `__init__`) and remove it in `__exit__`
regardless of whether an exception occurred. Store intermediate files,
thumbnails, and archive PDFs inside this directory.

```python
import shutil
import tempfile
from pathlib import Path
from typing import Self
from types import TracebackType

from django.conf import settings

class MyCustomParser:
    ...

    def __init__(self, logging_group: object = None) -> None:
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self._tempdir = Path(
            tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR)
        )
        self._text: str | None = None
        self._archive_path: Path | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)
```

**Optional context — `configure()`**

The consumer calls `configure()` with a `ParserContext` after instantiation
and before `parse()`. If your parser doesn't need context, a no-op
implementation is fine:

```python
from paperless.parsers import ParserContext

def configure(self, context: ParserContext) -> None:
    pass   # override if you need context.mailrule_id, etc.
```

**Parsing**

`parse()` is the core method. It must not return a value; instead, store
results in instance attributes and expose them via the accessor methods below.
Raise `documents.parsers.ParseError` on any unrecoverable failure.

```python
from documents.parsers import ParseError

def parse(
    self,
    document_path: Path,
    mime_type: str,
    *,
    produce_archive: bool = True,
) -> None:
    try:
        self._text = extract_text_from_my_format(document_path)
    except Exception as e:
        raise ParseError(f"Failed to parse {document_path}: {e}") from e

    if produce_archive and self.can_produce_archive:
        archive = self._tempdir / "archived.pdf"
        convert_to_pdf(document_path, archive)
        self._archive_path = archive
```

**Result accessors**

```python
def get_text(self) -> str | None:
    return self._text

def get_date(self) -> "datetime.datetime | None":
    # Return a datetime extracted from the document, or None to let
    # Paperless-ngx use its default date-guessing logic.
    return None

def get_archive_path(self) -> Path | None:
    return self._archive_path

def get_page_count(self, document_path: Path, mime_type: str) -> int | None:
    # If the format doesn't have the concept of pages, return None
    return count_pages(document_path)

```

**Thumbnail**

`get_thumbnail()` may be called independently of `parse()`. Return the path
to a WebP image inside `self._tempdir`. The image should be roughly 500 × 700
pixels.

```python
def get_thumbnail(self, document_path: Path, mime_type: str) -> Path:
    thumb = self._tempdir / "thumb.webp"
    render_thumbnail(document_path, thumb)
    return thumb
```

**Optional methods**

These are called by the API on demand, not during the consumption pipeline.
Implement them if your format supports the information; otherwise return
`None` / `[]`.

```python

def extract_metadata(
    self,
    document_path: Path,
    mime_type: str,
) -> "list[MetadataEntry]":
    # Must never raise. Return [] if metadata cannot be read.
    from paperless.parsers import MetadataEntry
    return [
        MetadataEntry(
            namespace="https://example.com/ns/",
            prefix="ex",
            key="Author",
            value="Alice",
        )
    ]
```

#### 2. Registering via entry point

Add the following to your package's `pyproject.toml`. The key (left of `=`)
is an arbitrary name used only in log output; the value is the
`module:ClassName` import path.

```toml
[project.entry-points."paperless_ngx.parsers"]
my_parser = "my_package.parsers:MyCustomParser"
```

Install your package into the same Python environment as Paperless-ngx (or
add it to the Docker image), and the parser will be discovered automatically
on the next startup. No configuration changes are needed.

To verify discovery, check the application logs at startup for a line like:

```
Loaded third-party parser 'My Format Parser' v1.0.0 by Acme Corp (entrypoint: 'my_parser').
```

#### 3. Utilities

`paperless.parsers.utils` provides helpers you can import directly:

| Function                                | Description                                                      |
| --------------------------------------- | ---------------------------------------------------------------- |
| `read_file_handle_unicode_errors(path)` | Read a file as UTF-8, replacing invalid bytes instead of raising |
| `get_page_count_for_pdf(path)`          | Count pages in a PDF using pikepdf                               |
| `extract_pdf_metadata(path)`            | Extract XMP metadata from a PDF as a `list[MetadataEntry]`       |

#### Minimal example

A complete, working parser for a hypothetical plain-XML format:

```python
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Self
from types import TracebackType
import xml.etree.ElementTree as ET

from django.conf import settings

from documents.parsers import ParseError
from paperless.parsers import ParserContext


class XmlDocumentParser:
    name    = "XML Parser"
    version = "1.0.0"
    author  = "Acme Corp"
    url     = "https://example.com/xml-parser"

    @classmethod
    def supported_mime_types(cls) -> dict[str, str]:
        return {"application/xml": ".xml", "text/xml": ".xml"}

    @classmethod
    def score(cls, mime_type: str, filename: str, path: Path | None = None) -> int | None:
        return 10

    @property
    def can_produce_archive(self) -> bool:
        return False

    @property
    def requires_pdf_rendition(self) -> bool:
        return False

    def __init__(self, logging_group: object = None) -> None:
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self._tempdir = Path(tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR))
        self._text: str | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def configure(self, context: ParserContext) -> None:
        pass

    def parse(self, document_path: Path, mime_type: str, *, produce_archive: bool = True) -> None:
        try:
            tree = ET.parse(document_path)
            self._text = " ".join(tree.getroot().itertext())
        except ET.ParseError as e:
            raise ParseError(f"XML parse error: {e}") from e

    def get_text(self) -> str | None:
        return self._text

    def get_date(self):
        return None

    def get_archive_path(self) -> Path | None:
        return None

    def get_thumbnail(self, document_path: Path, mime_type: str) -> Path:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (500, 700), color="white")
        ImageDraw.Draw(img).text((10, 10), "XML Document", fill="black")
        out = self._tempdir / "thumb.webp"
        img.save(out, format="WEBP")
        return out

    def get_page_count(self, document_path: Path, mime_type: str) -> int | None:
        return None

    def extract_metadata(self, document_path: Path, mime_type: str) -> list:
        return []
```

### Developing date parser plugins

Paperless-ngx uses a plugin system for date parsing, allowing you to extend or replace the default date parsing behavior. Plugins are discovered using [Python entry points](https://setuptools.pypa.io/en/latest/userguide/entry_point.html).

#### Creating a Date Parser Plugin

To create a custom date parser plugin, you need to:

1. Create a class that inherits from `DateParserPluginBase`
2. Implement the required abstract method
3. Register your plugin via an entry point

##### 1. Implementing the Parser Class

Your parser must extend `documents.plugins.date_parsing.DateParserPluginBase` and implement the `parse` method:

```python
from collections.abc import Iterator
import datetime

from documents.plugins.date_parsing import DateParserPluginBase


class MyDateParserPlugin(DateParserPluginBase):
    """
    Custom date parser implementation.
    """

    def parse(self, filename: str, content: str) -> Iterator[datetime.datetime]:
        """
        Parse dates from the document's filename and content.

        Args:
            filename: The original filename of the document
            content: The extracted text content of the document

        Yields:
            datetime.datetime: Valid datetime objects found in the document
        """
        # Your parsing logic here
        # Use self.config to access configuration settings

        # Example: parse dates from filename first
        if self.config.filename_date_order:
            # Your filename parsing logic
            yield some_datetime

        # Then parse dates from content
        # Your content parsing logic
        yield another_datetime
```

##### 2. Configuration and Helper Methods

Your parser instance is initialized with a `DateParserConfig` object accessible via `self.config`. This provides:

- `languages: list[str]` - List of language codes for date parsing
- `timezone_str: str` - Timezone string for date localization
- `ignore_dates: set[datetime.date]` - Dates that should be filtered out
- `reference_time: datetime.datetime` - Current time for filtering future dates
- `filename_date_order: str | None` - Date order preference for filenames (e.g., "DMY", "MDY")
- `content_date_order: str` - Date order preference for content

The base class provides two helper methods you can use:

```python
def _parse_string(
    self,
    date_string: str,
    date_order: str,
) -> datetime.datetime | None:
    """
    Parse a single date string using dateparser with configured settings.
    """

def _filter_date(
    self,
    date: datetime.datetime | None,
) -> datetime.datetime | None:
    """
    Validate a parsed datetime against configured rules.
    Filters out dates before 1900, future dates, and ignored dates.
    """
```

##### 3. Resource Management (Optional)

If your plugin needs to acquire or release resources (database connections, API clients, etc.), override the context manager methods. Paperless-ngx will always use plugins as context managers, ensuring resources can be released even in the event of errors.

##### 4. Registering Your Plugin

Register your plugin using a setuptools entry point in your package's `pyproject.toml`:

```toml
[project.entry-points."paperless_ngx.date_parsers"]
my_parser = "my_package.parsers:MyDateParserPlugin"
```

The entry point name (e.g., `"my_parser"`) is used for sorting when multiple plugins are found. Paperless-ngx will use the first plugin alphabetically by name if multiple plugins are discovered.

#### Plugin Discovery

Paperless-ngx automatically discovers and loads date parser plugins at runtime. The discovery process:

1. Queries the `paperless_ngx.date_parsers` entry point group
2. Validates that each plugin is a subclass of `DateParserPluginBase`
3. Sorts valid plugins alphabetically by entry point name
4. Uses the first valid plugin, or falls back to the default `RegexDateParserPlugin` if none are found

If multiple plugins are installed, a warning is logged indicating which plugin was selected.

#### Example: Simple Date Parser

Here's a minimal example that only looks for ISO 8601 dates:

```python
import datetime
import re
from collections.abc import Iterator

from documents.plugins.date_parsing.base import DateParserPluginBase


class ISODateParserPlugin(DateParserPluginBase):
    """
    Parser that only matches ISO 8601 formatted dates (YYYY-MM-DD).
    """

    ISO_REGEX = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

    def parse(self, filename: str, content: str) -> Iterator[datetime.datetime]:
        # Combine filename and content for searching
        text = f"{filename} {content}"

        for match in self.ISO_REGEX.finditer(text):
            date_string = match.group(1)
            # Use helper method to parse with configured timezone
            date = self._parse_string(date_string, "YMD")
            # Use helper method to validate the date
            filtered_date = self._filter_date(date)
            if filtered_date is not None:
                yield filtered_date
```

## Using Visual Studio Code devcontainer

Another easy way to get started with development is to use Visual Studio
Code devcontainers. This approach will create a preconfigured development
environment with all of the required tools and dependencies.
[Learn more about devcontainers](https://code.visualstudio.com/docs/devcontainers/containers).
The .devcontainer/vscode/tasks.json and .devcontainer/vscode/launch.json files
contain more information about the specific tasks and launch configurations (see the
non-standard "description" field).

To get started:

1. Clone the repository on your machine and open the Paperless-ngx folder in VS Code.

2. VS Code will prompt you with "Reopen in container". Do so and wait for the environment to start.

3. In case your host operating system is Windows:
   - The Source Control view in Visual Studio Code might show: "The detected Git repository is potentially unsafe as the folder is owned by someone other than the current user." Use "Manage Unsafe Repositories" to fix this.
   - Git might have detecteded modifications for all files, because Windows is using CRLF line endings. Run `git checkout .` in the containers terminal to fix this issue.

4. Initialize the project by running the task **Project Setup: Run all Init Tasks**. This
   will initialize the database tables and create a superuser. Then you can compile the front end
   for production or run the frontend in debug mode.

5. The project is ready for debugging, start either run the fullstack debug or individual debug
   processes. Yo spin up the project without debugging run the task **Project Start: Run all Services**
