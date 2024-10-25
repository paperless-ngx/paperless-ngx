# Contributing

If you feel like contributing to the project, please do! Bug fixes and improvements are always welcome.

If you want to implement something big:

- Please start a discussion about that in the issues! Maybe something similar is already in development and we can make it happen together.
- When making additions to the project, consider if the majority of users will benefit from your change. If not, you're probably better of forking the project.
- Also consider if your change will get in the way of other users. A good change is a change that enhances the experience of some users who want that change and does not affect users who do not care about the change.
- Please see the [paperless-ngx merge process](#merging-prs) below.

## Python

Paperless supports python 3.10 - 3.12 at this time. We format Python code with [ruff](https://docs.astral.sh/ruff/formatter/).

## Branches

`main` always reflects the latest release. Apart from changes to the documentation or readme, absolutely no functional changes on this branch in between releases.

`dev` contains all changes that will be part of the next release. Use this branch to start making your changes.

`feature-X` branches are for experimental stuff that will eventually be merged into dev.

## Testing:

Please format and test your code! I know it's a hassle, but it makes sure that your code works now and will allow us to detect regressions easily.

To test your code, execute `pytest` in the src/ directory. This also generates a html coverage report, which you can use to see if you missed anything important during testing.

Before you can run `pytest`, ensure to [properly set up your local environment](https://docs.paperless-ngx.com/development/#initial-setup-and-first-start).

## More info:

... is available [in the documentation](https://docs.paperless-ngx.com/development).

# Merging PRs

Once you have submitted a **P**ull **R**equest it will be reviewed, approved, and merged by one or more community members of any team. Automated code tests and formatting checks must be passed.

## Non-Trivial Requests

PRs deemed `non-trivial` will go through a stricter review process before being merged into `dev`. This is to ensure code quality and complete functionality (free of side effects).

Examples of `non-trivial` PRs might include:

- Additional features
- Large changes to many distinct files
- Breaking or deprecation of existing features

Our community review process for `non-trivial` PRs is the following:

1. Must pass usual automated code tests and formatting checks.
2. The PR will be assigned and pinged to the appropriately experienced team (i.e. @paperless-ngx/backend for backend changes).
3. Development team will check and test code manually (possibly over several days).
   - You may be asked to make changes or rebase.
   - The team may ask for additional testing done by @paperless-ngx/test
4. **At least two** members of the team will approve and finally merge the request into `dev` 🎉.

This process might be slow as community members have different schedules and time to dedicate to the Paperless project. However it ensures community code reviews are as brilliantly thorough as they once were with @jonaswinkler.

# AI-Generated Code

This project does not specifically prohibit the use of AI-generated code _during the process_ of creating a PR, however:

1. Any code present in the final PR that was generated using AI sources should be clearly attributed as such and must not violate copyright protections.
2. We will not accept PRs that are entirely or mostly AI-derived.

# Translating Paperless-ngx

Some notes about translation:

- There are two resources:
  - `src-ui/messages.xlf` contains the translation strings for the front end. This is the most important.
  - `django.po` contains strings for the administration section of paperless, which is nice to have translated.
- Most of the front-end strings are used on buttons, menu items, etc., so ideally the translated string should not be much longer than the English original.
- Translation units may contain placeholders. These usually mean that there's a name of a tag or document or something in the string. You can click on the placeholders to copy them.
- Translation units may contain plural expressions such as `{PLURAL_VAR, plural, =1 {one result} =0 {no results} other {<placeholder> results}}`. Copy these verbatim and translate only the content in the inner `{}` brackets. Example: `{PLURAL_VAR, plural, =1 {Ein Ergebnis} =0 {Keine Ergebnisse} other {<placeholder> Ergebnisse}}`
- Changes to translations on Crowdin will get pushed into the repository automatically.

## Adding new languages to the codebase

If a language has already been added, and you would like to contribute new translations or change existing translations, please read the "Translation" section in the README.md file for further details on that.

If you would like the project to be translated to another language, first head over to https://crwd.in/paperless-ngx to check if that language has already been enabled for translation.
If not, please request the language to be added by creating an issue on GitHub. The issue should contain:

- English name of the language (the localized name can be added on Crowdin).
- ISO language code. A list of those can be found here: https://support.crowdin.com/enterprise/language-codes/
- Date format commonly used for the language, e.g. dd/mm/yyyy, mm/dd/yyyy, etc.

After the language has been added and some translations have been made on Crowdin, the language needs to be enabled in the code.
Note that there is no need to manually add a .po of .xlf file as those will be automatically generated and imported from Crowdin.
The following files need to be changed:

- src-ui/angular.json (under the _projects/paperless-ui/i18n/locales_ JSON key)
- src/paperless/settings.py (in the _LANGUAGES_ array)
- src-ui/src/app/services/settings.service.ts (inside the _LANGUAGE_OPTIONS_ array)
- src-ui/src/app/app.module.ts (import locale from _angular/common/locales_ and call _registerLocaleData_)

Please add the language in the correct order, alphabetically by locale.
Note that _en-us_ needs to stay on top of the list, as it is the default project language

If you are familiar with Git, feel free to send a Pull Request with those changes.
If not, let us know in the issue you created for the language, so that another developer can make these changes.

# Organization Structure & Membership

Paperless-ngx is a community project. We do our best to delegate permission and responsibility among a team of people to ensure the longevity of the project.

## Structure

As of writing, there are 21 members in paperless-ngx. 4 of these people have complete administrative privileges to the repo:

- [@shamoon](https://github.com/shamoon)
- [@bauerj](https://github.com/bauerj)
- [@qcasey](https://github.com/qcasey)
- [@FrankStrieter](https://github.com/FrankStrieter)

There are 5 teams collaborating on specific tasks within paperless-ngx:

- @paperless-ngx/backend (Python / django)
- @paperless-ngx/frontend (JavaScript / Typescript)
- @paperless-ngx/ci-cd (GitHub Actions / Deployment)
- @paperless-ngx/issues (Issue triage)
- @paperless-ngx/test (General testing for larger PRs)

## Permissions

All team members are notified when mentioned or assigned to a relevant issue or pull request. Additionally, each team has slightly different access to paperless-ngx:

- The **test** team has no special permissions.
- The **issues** team has `triage` access. This means they can organize issues and pull requests.
- The **backend**, **frontend**, and **ci-cd** teams have `write` access. This means they can approve PRs and push code, containers, releases, and more.

## Joining

We are not overly strict with inviting people to the organization. If you have read the [team permissions](#permissions) and think having additional access would enhance your contributions, please reach out to an [admin](#structure) of the team.

The admins occasionally invite contributors directly if we believe having them on a team will accelerate their work.

# Automatic Repository Maintenance

The Paperless-ngx team appreciates all effort and interest from the community in filing bug reports, creating feature requests, sharing ideas and helping other
community members. That said, in an effort to keep the repository organized and managebale the project uses automatic handling of certain areas:

- Issues that cannot be reproduced will be marked 'stale' after 7 days of inactivity and closed after 14 further days of inactivity.
- Issues, pull requests and discussions that are closed will be locked after 30 days of inactivity.
- Discussions with a marked answer will be automatically closed.
- Discussions in the 'General' or 'Support' categories will be closed after 180 days of inactivity.
- Feature requests that do not meet the following thresholds will be closed: 180 days of inactivity, < 5 "up-votes" after 180 days, < 20 "up-votes" after 1 year or < 80 "up-votes" at 2 years.

In all cases, threads can be re-opened by project maintainers and, of course, users can always create a new discussion for related concerns.
Finally, remember that all information remains searchable and 'closed' feature requests can still serve as inspiration for new features.

Thank you all for your contributions.
