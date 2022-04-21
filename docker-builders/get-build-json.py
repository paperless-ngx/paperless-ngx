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

CONFIG: Final = {
    # All packages need to be in the dict, even if not configured further
    # as it is used for the possible choices in the argument
    "psycopg2": {},
    "frontend": {},
    # Most information about Python packages comes from the Pipfile.lock
    # Excpetion being pikepdf, which needs a specific qpdf
    "pikepdf": {
        "qpdf_version": "10.6.3",
    },
    # For other packages, version and Git information are directly configured
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

    # Use the basic ref name, minus refs/heads or refs/tags for frontend builder image
    elif args.package == "frontend":
        output["version"] = os.environ["GITHUB_REF_NAME"]

    # Add anything special from the config
    output.update(CONFIG[args.package])

    # Based on the package and environment, generate the Docker image tag
    output["image_tag"] = _get_image_tag(repo_name, args.package, output["version"])

    # Output the JSON info to stdout
    print(json.dumps(output))


if __name__ == "__main__":
    _main()
