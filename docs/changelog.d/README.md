Add a news fragment for each pull request:

docs/changelog.d/<pr-number>.<type>.md

Types: breaking, notable, feature, bugfix, doc, misc

Example: docs/changelog.d/1234.bugfix.md
Content: Fixed the thing that broke when X happened. By @yourusername

If you haven't opened the PR yet, use a + prefix as a placeholder:

docs/changelog.d/+my-change.bugfix.md

Rename it to the real PR number once the PR exists.
