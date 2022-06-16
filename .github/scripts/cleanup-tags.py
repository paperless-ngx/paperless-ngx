#!/usr/bin/env python3
"""
When a feature branch is created, a new GitHub container is built and tagged
with the feature branch name.  When a feature branch is deleted, either through
a merge or deletion, the old image tag will still exist.

Though this isn't a problem for storage size, etc, it does lead to a long list
of tags which are no longer relevant and the last released version is pushed
 further and further down that list.

This script utlizes the GitHub API (through the gh cli application) to list the
package versions (aka tags) and the repository branches.  Then it removes feature
tags which have no matching branch

This pruning is applied to the primary package, the frontend builder package and the
frontend build cache package.

"""
import argparse
import logging
import os.path
import pprint
from typing import Dict
from typing import Final
from typing import List

from common import get_log_level
from ghapi.all import GhApi
from ghapi.all import paged


def _get_feature_packages(
    logger: logging.Logger,
    api: GhApi,
    is_org_repo: bool,
    repo_owner: str,
    package_name: str,
) -> Dict:
    """
    Uses the GitHub packages API endpoint data filter to containers
    which have a tag starting with "feature-"
    """

    # Get all package versions
    pkg_versions = []
    if is_org_repo:

        for pkg_version in paged(
            api.packages.get_all_package_versions_for_package_owned_by_org,
            org=repo_owner,
            package_type="container",
            package_name=package_name,
        ):
            pkg_versions.extend(pkg_version)
    else:
        for pkg_version in paged(
            api.packages.get_all_package_versions_for_package_owned_by_authenticated_user,  # noqa: E501
            package_type="container",
            package_name=package_name,
        ):
            pkg_versions.extend(pkg_version)

    logger.debug(f"Found {len(pkg_versions)} package versions for {package_name}")

    # Filter to just those containers tagged "feature-"
    feature_versions = {}

    for item in pkg_versions:
        is_feature_version = False
        feature_tag_name = None
        if (
            "metadata" in item
            and "container" in item["metadata"]
            and "tags" in item["metadata"]["container"]
        ):
            for tag in item["metadata"]["container"]["tags"]:
                if tag.startswith("feature-"):
                    feature_tag_name = tag
                    is_feature_version = True
        if is_feature_version:
            logger.info(
                f"Located feature tag: {feature_tag_name} for image {package_name}",
            )
            # logger.debug(pprint.pformat(item, indent=2))
            feature_versions[feature_tag_name] = item
        else:
            logger.debug(f"Filtered {pprint.pformat(item, indent=2)}")

    logger.info(
        f"Found {len(feature_versions)} package versions for"
        f" {package_name} with feature tags",
    )

    return feature_versions


def _main():

    parser = argparse.ArgumentParser(
        description="Using the GitHub API locate and optionally delete container"
        " tags which no longer have an associated feature branch",
    )

    parser.add_argument(
        "--delete",
        action="store_true",
        default=False,
        help="If provided, actually delete the container tags",
    )

    parser.add_argument(
        "--loglevel",
        default="info",
        help="Configures the logging level",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=get_log_level(args),
        datefmt="%Y-%m-%d %H:%M:%S",
        format="%(asctime)s %(levelname)-8s %(message)s",
    )

    logger = logging.getLogger("cleanup-tags")

    repo: Final[str] = os.environ["GITHUB_REPOSITORY"]
    repo_owner: Final[str] = os.environ["GITHUB_REPOSITORY_OWNER"]

    is_org_repo: Final[bool] = repo_owner == "paperless-ngx"
    dry_run: Final[bool] = not args.delete

    logger.debug(f"Org Repo? {is_org_repo}")
    logger.debug(f"Dry Run? {dry_run}")

    api = GhApi(
        owner=repo_owner,
        repo=os.path.basename(repo),
        token=os.environ["GITHUB_TOKEN"],
    )

    pkg_list: Final[List[str]] = [
        "paperless-ngx",
        # TODO: It would be nice to cleanup additional packages, but we can't
        # see https://github.com/fastai/ghapi/issues/84
        # "builder/frontend",
        # "builder-frontend-cache",
    ]

    # Get the list of current "feature-" branches
    feature_branch_info = api.list_branches(prefix="feature-")
    feature_branch_names = []
    for branch in feature_branch_info:
        name_only = branch["ref"].removeprefix("refs/heads/")
        logger.info(f"Located feature branch: {name_only}")
        feature_branch_names.append(name_only)

    logger.info(f"Located {len(feature_branch_names)} feature branches")

    # TODO The deletion doesn't yet actually work
    # See https://github.com/fastai/ghapi/issues/132
    # This would need to be updated to use gh cli app or requests or curl
    # or something
    if is_org_repo:
        endpoint = (
            "https://api.github.com/orgs/{ORG}/packages/container/{name}/versions/{id}"
        )
    else:
        endpoint = "https://api.github.com/user/packages/container/{name}/{id}"

    for package_name in pkg_list:

        logger.info(f"Processing image {package_name}")

        # Get the list of images tagged with "feature-"
        feature_packages = _get_feature_packages(
            logger,
            api,
            is_org_repo,
            repo_owner,
            package_name,
        )

        # Get the set of container tags without matching feature branches
        to_delete = list(set(feature_packages.keys()) - set(feature_branch_names))

        for container_tag in to_delete:
            container_info = feature_packages[container_tag]

            formatted_endpoint = endpoint.format(
                ORG=repo_owner,
                name=package_name,
                id=container_info["id"],
            )

            if dry_run:
                logger.info(
                    f"Would delete {package_name}:{container_tag} with"
                    f" id: {container_info['id']}",
                )
                # logger.debug(formatted_endpoint)
            else:
                logger.info(
                    f"Deleting {package_name}:{container_tag} with"
                    f" id: {container_info['id']}",
                )


if __name__ == "__main__":
    _main()
