<p align="center">
  <a href="https://getbootstrap.com/">
    <img src="https://getbootstrap.com/docs/5.2/assets/brand/bootstrap-logo-shadow.png" alt="Bootstrap logo" width="200" height="165">
  </a>
</p>

<h3 align="center">Bootstrap Icons</h3>

<p align="center">
  Official open source SVG icon library for Bootstrap with over 2,000 icons.
  <br>
  <a href="https://icons.getbootstrap.com/"><strong>Explore Bootstrap Icons »</strong></a>
  <br>
  <br>
  <a href="https://getbootstrap.com/">Bootstrap</a>
  ·
  <a href="https://themes.getbootstrap.com/">Themes</a>
  ·
  <a href="https://blog.getbootstrap.com/">Blog</a>
  <br>
</p>

[![Bootstrap Icons preview](https://github.com/twbs/icons/blob/main/.github/preview.png)](https://icons.getbootstrap.com/)

## Install

Bootstrap Icons are packaged up and published to npm. We only include the processed SVGs in this package—it's up to you and your team to implement. [Read our docs](https://icons.getbootstrap.com/) for usage instructions.

```shell
npm i bootstrap-icons
```

For those [using Packagist](https://packagist.org/packages/twbs/bootstrap-icons), you can also install Bootstrap Icons via Composer:

```shell
composer require twbs/bootstrap-icons
```

[Also available in Figma](https://www.figma.com/community/file/1042482994486402696/Bootstrap-Icons).

## Usage

Depending on your setup, you can include Bootstrap Icons in a handful of ways.

- Copy-paste SVGs as embedded HTML
- Reference via `<img>` element
- Use the SVG sprite
- Include via CSS

[See the docs for more information](https://icons.getbootstrap.com/#usage).

## Development

[![Build Status](https://img.shields.io/github/actions/workflow/status/twbs/icons/test.yml?branch=main&label=Tests&logo=github)](https://github.com/twbs/icons/actions/workflows/test.yml?query=workflow%3ATests+branch%3Amain)
[![npm version](https://img.shields.io/npm/v/bootstrap-icons?logo=npm&logoColor=fff)](https://www.npmjs.com/package/bootstrap-icons)

Clone the repo, install dependencies, and start the Hugo server locally.

```shell
git clone https://github.com/twbs/icons/
cd icons
npm i
npm start
```

Then open `http://localhost:4000` in your browser.

### npm scripts

Here are some key scripts you'll use during development. Be sure to look to our `package.json` or `npm run` output for a complete list of scripts.

| Script       | Description                                                                   |
|--------------|-------------------------------------------------------------------------------|
| `start`      | Alias for running `docs-serve`                                                |
| `docs-serve` | Starts a local Hugo server                                                    |
| `pages`      | Generates permalink pages for each icon with template Markdown                |
| `icons`      | Processes and optimizes SVGs in `icons` directory, generates fonts and sprite |

## Adding SVGs

Icons are typically only added by @mdo, but exceptions can be made. New glyphs are designed in Figma first on a 16x16px grid, then exported as flattened SVGs with `fill` (no stroke). Once a new SVG icon has been added to the `icons` directory, we use an npm script to:

1. Optimize our SVGs with SVGO.
2. Modify the SVGs source code, removing all attributes before setting new attributes and values in our preferred order.

Use `npm run icons` to run the script, run `npm run pages` to build permalink pages, complete those pages, and, finally, commit the results in a new branch for updating.

**Warning**: Please exclude any auto-generated files, like `font/**` and `bootstrap-icons.svg` from your branch because they cause conflicts, and we generally update the dist files before a release.

## Publishing

Documentation is published automatically when a new Git tag is published. See our [GitHub Actions](https://github.com/twbs/icons/tree/main/.github/workflows) and [`package.json`](https://github.com/twbs/icons/blob/main/package.json) for more information.

## License

[MIT](LICENSE)

## Author

[@mdo](https://github.com/mdo)
