# Contributing

If you feel like contributing to the project, please do! Bug fixes and improvements are always welcome.

If you want to implement something big: Please start a discussion about that in the issues! Maybe something similar is already in development and we can make it happen together.

* When making additions to the project, consider if the majority of users will benefit from your change. If not, you're probably better of forking the project.
* Also consider if your change will get in the way of other users. A good change is a change that enhances the experience of some users who want that change and does not affect users who do not care about the change.

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
