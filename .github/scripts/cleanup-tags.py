#!/usr/bin/env python3
import functools
import json
import logging
import os
import re
import shutil
import subprocess
from argparse import ArgumentParser
from typing import Dict
from typing import Final
from typing import List
from urllib.parse import quote

import requests
from common import get_log_level

logger = logging.getLogger("cleanup-tags")


class ContainerPackage:
    def __init__(self, data: Dict):
        self._data = data
        self.name = self._data["name"]
        self.id = self._data["id"]
        self.url = self._data["url"]
        self.tags = self._data["metadata"]["container"]["tags"]

    @functools.cached_property
    def untagged(self) -> bool:
        return len(self.tags) == 0

    @functools.cache
    def tag_matches(self, pattern: str) -> bool:
        for tag in self.tags:
            if re.match(pattern, tag) is not None:
                return True
        return False

    def __repr__(self):
        return f"Package {self.name}"


class GithubContainerRegistry:
    def __init__(
        self,
        session: requests.Session,
        token: str,
        owner_or_org: str,
    ):
        self._session: requests.Session = session
        self._token = token
        self._owner_or_org = owner_or_org
        # https://docs.github.com/en/rest/branches/branches
        self._BRANCHES_ENDPOINT = "https://api.github.com/repos/{OWNER}/{REPO}/branches"
        if self._owner_or_org == "paperless-ngx":
            # https://docs.github.com/en/rest/packages#get-all-package-versions-for-a-package-owned-by-an-organization
            self._PACKAGES_VERSIONS_ENDPOINT = "https://api.github.com/orgs/{ORG}/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions"
            # https://docs.github.com/en/rest/packages#delete-package-version-for-an-organization
            self._PACKAGE_VERSION_DELETE_ENDPOINT = "https://api.github.com/orgs/{ORG}/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions/{PACKAGE_VERSION_ID}"
        else:
            # https://docs.github.com/en/rest/packages#get-all-package-versions-for-a-package-owned-by-the-authenticated-user
            self._PACKAGES_VERSIONS_ENDPOINT = "https://api.github.com/user/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions"
            # https://docs.github.com/en/rest/packages#delete-a-package-version-for-the-authenticated-user
            self._PACKAGE_VERSION_DELETE_ENDPOINT = "https://api.github.com/user/packages/{PACKAGE_TYPE}/{PACKAGE_NAME}/versions/{PACKAGE_VERSION_ID}"

    def __enter__(self):
        """
        Sets up the required headers for auth and response
        type from the API
        """
        self._session.headers.update(
            {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {self._token}",
            },
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Ensures the authorization token is cleaned up no matter
        the reason for the exit
        """
        if "Accept" in self._session.headers:
            del self._session.headers["Accept"]
        if "Authorization" in self._session.headers:
            del self._session.headers["Authorization"]

    def _read_all_pages(self, endpoint):
        """
        Internal function to read all pages of an endpoint, utilizing the
        next.url until exhausted
        """
        internal_data = []

        while True:
            resp = self._session.get(endpoint)
            if resp.status_code == 200:
                internal_data += resp.json()
                if "next" in resp.links:
                    endpoint = resp.links["next"]["url"]
                else:
                    logger.debug("Exiting pagination loop")
                    break
            else:
                logger.warning(f"Request to {endpoint} return HTTP {resp.status_code}")
                break

        return internal_data

    def get_branches(self, repo: str):
        """
        Returns all current branches of the given repository
        """
        endpoint = self._BRANCHES_ENDPOINT.format(OWNER=self._owner_or_org, REPO=repo)
        internal_data = self._read_all_pages(endpoint)
        return internal_data

    def filter_branches_by_name_pattern(self, branch_data, pattern: str):
        """
        Filters the given list of branches to those which start with the given
        pattern.  Future enhancement could use regex patterns instead.
        """
        matches = {}

        for branch in branch_data:
            if branch["name"].startswith(pattern):
                matches[branch["name"]] = branch

        return matches

    def get_package_versions(
        self,
        package_name: str,
        package_type: str = "container",
    ) -> List[ContainerPackage]:
        """
        Returns all the versions of a given package (container images) from
        the API
        """
        package_name = quote(package_name, safe="")
        endpoint = self._PACKAGES_VERSIONS_ENDPOINT.format(
            ORG=self._owner_or_org,
            PACKAGE_TYPE=package_type,
            PACKAGE_NAME=package_name,
        )

        pkgs = []

        for data in self._read_all_pages(endpoint):
            pkgs.append(ContainerPackage(data))

        return pkgs

    def delete_package_version(self, package_data: ContainerPackage):
        """
        Deletes the given package version from the GHCR
        """
        resp = self._session.delete(package_data.url)
        if resp.status_code != 204:
            logger.warning(
                f"Request to delete {package_data.url} returned HTTP {resp.status_code}",
            )


def _main():
    parser = ArgumentParser(
        description="Using the GitHub API locate and optionally delete container"
        " tags which no longer have an associated feature branch",
    )

    # Requires an affirmative command to actually do a delete
    parser.add_argument(
        "--delete",
        action="store_true",
        default=False,
        help="If provided, actually delete the container tags",
    )

    # When a tagged image is updated, the previous version remains, but it no longer tagged
    # Add this option to remove them as well
    parser.add_argument(
        "--untagged",
        action="store_true",
        default=False,
        help="If provided, delete untagged containers as well",
    )

    # Allows configuration of log level for debugging
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

    # Must be provided in the environment
    repo_owner: Final[str] = os.environ["GITHUB_REPOSITORY_OWNER"]
    repo: Final[str] = os.environ["GITHUB_REPOSITORY"]
    gh_token: Final[str] = os.environ["TOKEN"]

    with requests.session() as sess:
        with GithubContainerRegistry(sess, gh_token, repo_owner) as gh_api:

            # Step 1 - Get branch information

            # Step 1.1 - Locate all branches of the repo
            all_branches = gh_api.get_branches("paperless-ngx")
            logger.info(f"Located {len(all_branches)} branches of {repo_owner}/{repo} ")

            # Step 1.2 - Filter branches to those starting with "feature-"
            feature_branches = gh_api.filter_branches_by_name_pattern(
                all_branches,
                "feature-",
            )
            logger.info(f"Located {len(feature_branches)} feature branches")

            # Step 2 - Deal with package information
            for package_name in ["paperless-ngx", "paperless-ngx/builder/cache/app"]:

                # Step 2.1 - Location all versions of the given package
                all_package_versions = gh_api.get_package_versions(package_name)

                # Faster lookup, map the tag to their container
                all_pkgs_tags_to_version = {}
                for pkg in all_package_versions:
                    for tag in pkg.tags:
                        all_pkgs_tags_to_version[tag] = pkg
                logger.info(
                    f"Located {len(all_package_versions)} versions of package {package_name}",
                )

                # Step 2.2 - Location package versions which have a tag of "feature-"
                packages_tagged_feature = []
                for package in all_package_versions:
                    if package.tag_matches("feature-"):
                        packages_tagged_feature.append(package)

                logger.info(
                    f'Located {len(packages_tagged_feature)} versions of package {package_name} tagged "feature-"',
                )

                # Faster lookup, map feature- tags to their container
                feature_pkgs_tags_to_versions = {}
                for pkg in packages_tagged_feature:
                    for tag in pkg.tags:
                        feature_pkgs_tags_to_versions[tag] = pkg

                # Step 2.3 - Determine which package versions have no matching branch and which tags we're keeping
                tags_to_delete = list(
                    set(feature_pkgs_tags_to_versions.keys())
                    - set(feature_branches.keys()),
                )
                tags_to_keep = list(
                    set(all_pkgs_tags_to_version.keys()) - set(tags_to_delete),
                )
                logger.info(
                    f"Located {len(tags_to_delete)} versions of package {package_name} to delete",
                )

                # Step 2.4 - Delete certain package versions
                for tag_to_delete in tags_to_delete:
                    package_version_info = feature_pkgs_tags_to_versions[tag_to_delete]

                    if args.delete:
                        logger.info(
                            f"Deleting {tag_to_delete} (id {package_version_info.id})",
                        )
                        gh_api.delete_package_version(
                            package_version_info,
                        )

                    else:
                        logger.info(
                            f"Would delete {tag_to_delete} (id {package_version_info.id})",
                        )

                # Step 3 - Deal with untagged and dangling packages
                if args.untagged:

                    """
                    Ok, bear with me, these are annoying.

                    Our images are multi-arch, so the manifest is more like a pointer to a sha256 digest.
                    These images are untagged, but pointed to, and so should not be removed (or every pull fails).

                    So for each image getting kept, parse the manifest to find the digest(s) it points to.  Then
                    remove those from the list of untagged images.  The final result is the untagged, not pointed to
                    version which should be safe to remove.

                    Example:
                        Tag: ghcr.io/paperless-ngx/paperless-ngx:1.7.1 refers to
                            amd64: sha256:b9ed4f8753bbf5146547671052d7e91f68cdfc9ef049d06690b2bc866fec2690
                            armv7: sha256:81605222df4ba4605a2ba4893276e5d08c511231ead1d5da061410e1bbec05c3
                            arm64: sha256:374cd68db40734b844705bfc38faae84cc4182371de4bebd533a9a365d5e8f3b
                        each of which appears as untagged image

                    """

                    # Step 3.1 - Simplify the untagged data, mapping name (which is a digest) to the version
                    untagged_versions = {}
                    for x in all_package_versions:
                        if x.untagged:
                            untagged_versions[x.name] = x

                    skips = 0
                    # Extra security to not delete on an unexpected error
                    actually_delete = True

                    logger.info(
                        f"Located {len(tags_to_keep)} tags of package {package_name} to keep",
                    )

                    # Step 3.2 - Parse manifests to locate digests pointed to
                    for tag in tags_to_keep:
                        full_name = f"ghcr.io/{repo_owner}/{package_name}:{tag}"
                        logger.info(f"Checking manifest for {full_name}")
                        try:
                            proc = subprocess.run(
                                [
                                    shutil.which("docker"),
                                    "manifest",
                                    "inspect",
                                    full_name,
                                ],
                                capture_output=True,
                            )

                            manifest_list = json.loads(proc.stdout)
                            for manifest in manifest_list["manifests"]:
                                digest = manifest["digest"]
                                platform_data_os = manifest["platform"]["os"]
                                platform_arch = manifest["platform"]["architecture"]
                                platform_variant = manifest["platform"].get(
                                    "variant",
                                    "",
                                )
                                platform = f"{platform_data_os}/{platform_arch}{platform_variant}"

                                if digest in untagged_versions:
                                    logger.debug(
                                        f"Skipping deletion of {digest}, referred to by {full_name} for {platform}",
                                    )
                                    del untagged_versions[digest]
                                    skips += 1

                        except json.decoder.JSONDecodeError as err:
                            # This is probably for a cache image, which isn't a multi-arch digest
                            # These are ok to delete all on
                            logger.debug(f"{err} on {full_name}")
                            continue
                        except Exception as err:
                            actually_delete = False
                            logger.exception(err)
                            continue

                    logger.info(f"Skipping deletion of {skips} packages")

                    # Step 3.3 - Delete the untagged and not pointed at packages
                    logger.info(f"Deleting untagged packages of {package_name}")
                    for to_delete_name in untagged_versions:
                        to_delete_version = untagged_versions[to_delete_name]

                        if args.delete and actually_delete:
                            logger.info(
                                f"Deleting id {to_delete_version.id} named {to_delete_version.name}",
                            )
                            gh_api.delete_package_version(
                                to_delete_version,
                            )
                        else:
                            logger.info(
                                f"Would delete {to_delete_name} (id {to_delete_version.id})",
                            )
                else:
                    logger.info("Leaving untagged images untouched")


if __name__ == "__main__":
    _main()
