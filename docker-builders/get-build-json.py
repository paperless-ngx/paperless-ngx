#!/usr/bin/env python3
"""
This is a helper script to either parse the JSON of the Pipfile.lock
or otherwise return a JSON object detailing versioning and image tags
for the packages we build seperately, then copy into the final Docker image
"""
import argparse
import json
import os
from pathlib import Path
from typing import Final

CONFIG: Final = {
    # All packages need to be in the dict, even if not configured further
    # as it is used for the possible choices in the argument
    "psycopg2": {},
    # Most information about Python packages comes from the Pipfile.lock
    "pikepdf": {
        "qpdf_version": "10.6.3",
    },
    # For other packages, it is directly configured, for now
    # These require manual updates to this file for version updates
    "qpdf": {
        "version": "10.6.3",
        "git_tag": "N/A",
    },
    "jbig2enc": {
        "version": "0.29",
        "git_tag": "0.29",
    },
}


def _get_image_tag(
    repo_name: str,
    pkg_name: str,
    pkg_version: str,
) -> str:
    return f"ghcr.io/{repo_name}/builder/{pkg_name}:{pkg_version}"


def _main():
    parser = argparse.ArgumentParser(
        description="Generate a JSON object of information required to build the given package, based on the Pipfile.lock",
    )
    parser.add_argument(
        "package",
        help="The name of the package to generate JSON for",
        choices=CONFIG.keys(),
    )

    args = parser.parse_args()

    pip_lock = Path("Pipfile.lock")

    repo_name = os.environ["GITHUB_REPOSITORY"]

    # The JSON object we'll output
    output = {"name": args.package}

    # Read Pipfile.lock file

    pipfile_data = json.loads(pip_lock.read_text())

    # Read the version from Pipfile.lock

    if args.package in pipfile_data["default"]:

        pkg_data = pipfile_data["default"][args.package]

        pkg_version = pkg_data["version"].split("==")[-1]

        output["version"] = pkg_version

        # Based on the package, generate the expected Git tag name

        if args.package == "pikepdf":
            git_tag_name = f"v{pkg_version}"
        elif args.package == "psycopg2":
            git_tag_name = pkg_version.replace(".", "_")

        output["git_tag"] = git_tag_name

        # Based on the package and environment, generate the Docker image tag

        image_tag = _get_image_tag(repo_name, args.package, pkg_version)

        output["image_tag"] = image_tag

        # Check for any special configuration, based on package

        if args.package in CONFIG:
            output.update(CONFIG[args.package])

    elif args.package in CONFIG:

        # This is not a Python package

        output.update(CONFIG[args.package])

        output["image_tag"] = _get_image_tag(repo_name, args.package, output["version"])

    else:
        raise NotImplementedError(args.package)

    # Output the JSON info to stdout

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    _main()
