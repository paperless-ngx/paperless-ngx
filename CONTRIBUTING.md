# Contributing

If you feel like contributing to the project, please do! Bug fixes and improvements are always welcome.

If you want to implement something big: 

* Please start a discussion about that in the issues! Maybe something similar is already in development and we can make it happen together.
* When making additions to the project, consider if the majority of users will benefit from your change. If not, you're probably better of forking the project.
* Also consider if your change will get in the way of other users. A good change is a change that enhances the experience of some users who want that change and does not affect users who do not care about the change.
* Please see the [paperless-ngx merge process](#merging-non-trivial-prs) below.

## Python

Paperless supports python 3.6, 3.7, 3.8 and 3.9.

## Branches

`master` always reflects the latest release. Apart from changes to the documentation or readme, absolutely no functional changes on this branch in between releases.

`dev` contains all changes that will be part of the next release. Use this branch to start making your changes.

`feature-X` branches are for experimental stuff that will eventually be merged into dev.

## Testing:

Please test your code! I know its a hassle, but it makes sure that your code works now and will allow us to detect regressions easily.

To test your code, execute `pytest` in the src/ directory. This also generates a html coverage report, which you can use to see if you missed anything important during testing.

## More info:

... is available in the documentation. https://paperless-ng.readthedocs.io/en/latest/extending.html

# Merging PRs

Once you have submitted a **P**ull **R**equest it will be reviewed, approved, and merged by one or more community members of any team. Automated code tests and formatting checks must be passed.

## Non-Trivial Requests

PRs deemed `non-trivial` will go through a stricter review process before being merged into `dev`. This is to ensure code quality and complete functionality (free of side effects).

Examples of `non-trivial` PRs might include:

* Additional features
* Large changes to many distinct files
* Breaking or depreciation of existing features

Our community review process for `non-trivial` prs is the following:

1. Must pass usual automated code tests and formatting checks.
2. The PR will be assigned and pinged to the appropriately experienced team (i.e. @paperless-ngx/backend for backend changes).
3. Development team will check and test code manually (possibly over several days).
   - You may be asked to make changes or rebase. 
   - The team may ask for additional testing done by @paperless-ngx/test
4. **Two or three** members of the team will approve and finally merge the request into `dev` 🎉.

This process might be slow as community members have different schedules and time to dedicate to the Paperless project. However it ensures community code reviews are as brilliantly thorough as they once were with @jonaswinkler.
