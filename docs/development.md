# Development

This section describes the steps you need to take to start development
on Paperless-ngx.

Check out the source from GitHub. The repository is organized in the
following way:

-   `main` always represents the latest release and will only see
    changes when a new release is made.
-   `dev` contains the code that will be in the next release.
-   `feature-X` contains bigger changes that will be in some release, but
    not necessarily the next one.

When making functional changes to Paperless-ngx, _always_ make your changes
on the `dev` branch.

Apart from that, the folder structure is as follows:

-   `docs/` - Documentation.
-   `src-ui/` - Code of the front end.
-   `src/` - Code of the back end.
-   `scripts/` - Various scripts that help with different parts of
    development.
-   `docker/` - Files required to build the docker image.

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
    $ uv sync --group dev
    ```

5.  Install pre-commit hooks:

    ```bash
    $ uv run prek install
    ```

6.  Apply migrations and create a superuser (also can be done via the web UI) for your development instance:

    ```bash
    # src/

    $ uv run manage.py migrate
    $ uv run manage.py createsuperuser
    ```

7.  You can now either ...

    -   install Redis or

    -   use the included `scripts/start_services.sh` to use Docker to fire
        up a Redis instance (and some other services such as Tika,
        Gotenberg and a database server) or

    -   spin up a bare Redis container

        ```
        docker run -d -p 6379:6379 --restart unless-stopped redis:latest
        ```

8.  Continue with either back-end or front-end development – or both :-).

## Back end development

The back end is a [Django](https://www.djangoproject.com/) application.
[PyCharm](https://www.jetbrains.com/de-de/pycharm/) as well as [Visual Studio Code](https://code.visualstudio.com)
work well for development, but you can use whatever you want.

Configure the IDE to use the `src/`-folder as the base source folder.
Configure the following launch configurations in your IDE:

-   `python3 manage.py runserver`
-   `python3 manage.py document_consumer`
-   `celery --app paperless worker -l DEBUG` (or any other log level)

To start them all:

```bash
# src/

$ python3 manage.py runserver & \
  python3 manage.py document_consumer & \
  celery --app paperless worker -l DEBUG
```

You might need the front end to test your back end code.
This assumes that you have AngularJS installed on your system.
Go to the [Front end development](#front-end-development) section for further details.
To build the front end once use this command:

```bash
# src-ui/

$ pnpm install
$ ng build --configuration production
```

### Testing

-   Run `pytest` in the `src/` directory to execute all tests. This also
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
    ng serve
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
$ git ls-files -- '*.ts' | xargs prek run prettier --files
```

Front end testing uses Jest and Playwright. Unit tests and e2e tests,
respectively, can be run non-interactively with:

```bash
$ ng test
$ npx playwright test
```

Playwright also includes a UI which can be run with:

```bash
$ npx playwright test --ui
```

### Building the frontend

In order to build the front end and serve it as part of Django, execute:

```bash
$ ng build --configuration production
```

This will build the front end and put it in a location from which the
Django server will serve it as static content. This way, you can verify
that authentication is working.

## Localization

Paperless-ngx is available in many different languages. Since Paperless-ngx
consists both of a Django application and an AngularJS front end, both
these parts have to be translated separately.

### Front end localization

-   The AngularJS front end does localization according to the [Angular
    documentation](https://angular.io/guide/i18n).
-   The source language of the project is "en_US".
-   The source strings end up in the file `src-ui/messages.xlf`.
-   The translated strings need to be placed in the
    `src-ui/src/locale/` folder.
-   In order to extract added or changed strings from the source files,
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

-   The django application does localization according to the [Django
    documentation](https://docs.djangoproject.com/en/3.1/topics/i18n/translation/).
-   The source language of the project is "en_US".
-   Localization files end up in the folder `src/locale/`.
-   In order to extract strings from the application, call
    `python3 manage.py makemessages -l en_US`. This is important after
    making changes to translatable strings.
-   The message files need to be compiled for them to show up in the
    application. Call `python3 manage.py compilemessages` to do this.
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

## Building the Docker image

The docker image is primarily built by the GitHub actions workflow, but
it can be faster when developing to build and tag an image locally.

Make sure you have the `docker-buildx` package installed. Building the image works as with any image:

```
docker build --file Dockerfile --tag paperless:local .
```

## Extending Paperless-ngx

Paperless-ngx does not have any fancy plugin systems and will probably never
have. However, some parts of the application have been designed to allow
easy integration of additional features without any modification to the
base code.

### Making custom parsers

Paperless-ngx uses parsers to add documents. A parser is
responsible for:

-   Retrieving the content from the original
-   Creating a thumbnail
-   _optional:_ Retrieving a created date from the original
-   _optional:_ Creating an archived document from the original

Custom parsers can be added to Paperless-ngx to support more file types. In
order to do that, you need to write the parser itself and announce its
existence to Paperless-ngx.

The parser itself must extend `documents.parsers.DocumentParser` and
must implement the methods `parse` and `get_thumbnail`. You can provide
your own implementation to `get_date` if you don't want to rely on
Paperless-ngx' default date guessing mechanisms.

```python
class MyCustomParser(DocumentParser):

    def parse(self, document_path, mime_type):
        # This method does not return anything. Rather, you should assign
        # whatever you got from the document to the following fields:

        # The content of the document.
        self.text = "content"

        # Optional: path to a PDF document that you created from the original.
        self.archive_path = os.path.join(self.tempdir, "archived.pdf")

        # Optional: "created" date of the document.
        self.date = get_created_from_metadata(document_path)

    def get_thumbnail(self, document_path, mime_type):
        # This should return the path to a thumbnail you created for this
        # document.
        return os.path.join(self.tempdir, "thumb.webp")
```

If you encounter any issues during parsing, raise a
`documents.parsers.ParseError`.

The `self.tempdir` directory is a temporary directory that is guaranteed
to be empty and removed after consumption finished. You can use that
directory to store any intermediate files and also use it to store the
thumbnail / archived document.

After that, you need to announce your parser to Paperless-ngx. You need to
connect a handler to the `document_consumer_declaration` signal. Have a
look in the file `src/paperless_tesseract/apps.py` on how that's done.
The handler is a method that returns information about your parser:

```python
def myparser_consumer_declaration(sender, **kwargs):
    return {
        "parser": MyCustomParser,
        "weight": 0,
        "mime_types": {
            "application/pdf": ".pdf",
            "image/jpeg": ".jpg",
        }
    }
```

-   `parser` is a reference to a class that extends `DocumentParser`.
-   `weight` is used whenever two or more parsers are able to parse a
    file: The parser with the higher weight wins. This can be used to
    override the parsers provided by Paperless-ngx.
-   `mime_types` is a dictionary. The keys are the mime types your
    parser supports and the value is the default file extension that
    Paperless-ngx should use when storing files and serving them for
    download. We could guess that from the file extensions, but some
    mime types have many extensions associated with them and the Python
    methods responsible for guessing the extension do not always return
    the same value.

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

## Developing Date Parser Plugins

Paperless-ngx uses a plugin system for date parsing, allowing you to extend or replace the default date parsing behavior. Plugins are discovered using [Python entry points](https://setuptools.pypa.io/en/latest/userguide/entry_point.html).

### Creating a Date Parser Plugin

To create a custom date parser plugin, you need to:

1. Create a class that inherits from `DateParserPluginBase`
2. Implement the required abstract method
3. Register your plugin via an entry point

#### 1. Implementing the Parser Class

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

#### 2. Configuration and Helper Methods

Your parser instance is initialized with a `DateParserConfig` object accessible via `self.config`. This provides:

-   `languages: list[str]` - List of language codes for date parsing
-   `timezone_str: str` - Timezone string for date localization
-   `ignore_dates: set[datetime.date]` - Dates that should be filtered out
-   `reference_time: datetime.datetime` - Current time for filtering future dates
-   `filename_date_order: str | None` - Date order preference for filenames (e.g., "DMY", "MDY")
-   `content_date_order: str` - Date order preference for content

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

#### 3. Resource Management (Optional)

If your plugin needs to acquire or release resources (database connections, API clients, etc.), override the context manager methods. Paperless-ngx will always use plugins as context managers, ensuring resources can be released even in the event of errors.

#### 4. Registering Your Plugin

Register your plugin using a setuptools entry point in your package's `pyproject.toml`:

```toml
[project.entry-points."paperless_ngx.date_parsers"]
my_parser = "my_package.parsers:MyDateParserPlugin"
```

The entry point name (e.g., `"my_parser"`) is used for sorting when multiple plugins are found. Paperless-ngx will use the first plugin alphabetically by name if multiple plugins are discovered.

### Plugin Discovery

Paperless-ngx automatically discovers and loads date parser plugins at runtime. The discovery process:

1. Queries the `paperless_ngx.date_parsers` entry point group
2. Validates that each plugin is a subclass of `DateParserPluginBase`
3. Sorts valid plugins alphabetically by entry point name
4. Uses the first valid plugin, or falls back to the default `RegexDateParserPlugin` if none are found

If multiple plugins are installed, a warning is logged indicating which plugin was selected.

### Example: Simple Date Parser

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
