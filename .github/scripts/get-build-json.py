#!/usr/bin/env python3
"""
This is a helper script for the mutli-stage Docker image builder.
It provides a single point of configuration for package version control.
The output JSON object is used by the CI workflow to determine what versions
to build and pull into the final Docker image.

Python package information is obtained from the Pipfile.lock.  As this is
kept updated by dependabot, it usually will need no further configuration.
The sole exception currently is pikepdf, which has a dependency on qpdf,
and is configured here to use the latest version of qpdf built by the workflow.

Other package version information is configured directly below, generally by
setting the version and Git information, if any.

"""
import argparse
import json
import os
from pathlib import Path
from typing import Final

from common import get_cache_image_tag
from common import get_image_tag


def _main():
    parser = argparse.ArgumentParser(
        description="Generate a JSON object of information required to build the given package, based on the Pipfile.lock",
    )
    parser.add_argument(
        "package",
        help="The name of the package to generate JSON for",
    )

    PIPFILE_LOCK_PATH: Final[Path] = Path("Pipfile.lock")
    BUILD_CONFIG_PATH: Final[Path] = Path(".build-config.json")

    # Read the main config file
    build_json: Final = json.loads(BUILD_CONFIG_PATH.read_text())

    # Read Pipfile.lock file
    pipfile_data: Final = json.loads(PIPFILE_LOCK_PATH.read_text())

    args: Final = parser.parse_args()

    # Read from environment variables set by GitHub Actions
    repo_name: Final[str] = os.environ["GITHUB_REPOSITORY"]
    branch_name: Final[str] = os.environ["GITHUB_REF_NAME"]

    # Default output values
    version = None
    extra_config = {}

    if args.package in pipfile_data["default"]:
        # Read the version from Pipfile.lock
        pkg_data = pipfile_data["default"][args.package]
        pkg_version = pkg_data["version"].split("==")[-1]
        version = pkg_version

        # Any extra/special values needed
        if args.package == "pikepdf":
            extra_config["qpdf_version"] = build_json["qpdf"]["version"]

    elif args.package in build_json:
        version = build_json[args.package]["version"]

    else:
        raise NotImplementedError(args.package)

    # The JSON object we'll output
    output = {
        "name": args.package,
        "version": version,
        "image_tag": get_image_tag(repo_name, args.package, version),
        "cache_tag": get_cache_image_tag(
            repo_name,
            args.package,
            version,
            branch_name,
        ),
    }

    # Add anything special a package may need
    output.update(extra_config)

    # Output the JSON info to stdout
    print(json.dumps(output))


if __name__ == "__main__":
    _main()
