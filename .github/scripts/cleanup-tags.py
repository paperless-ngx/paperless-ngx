#!/usr/bin/env python3
import json
import logging
import os
import shutil
import subprocess
from argparse import ArgumentParser
from typing import Dict
from typing import Final
from typing import List

from common import get_log_level
from github import ContainerPackage
from github import GithubBranchApi
from github import GithubContainerRegistryApi

logger = logging.getLogger("cleanup-tags")


class DockerManifest2:
    """
    Data class wrapping the Docker Image Manifest Version 2.

    See https://docs.docker.com/registry/spec/manifest-v2-2/
    """

    def __init__(self, data: Dict) -> None:
        self._data = data
        # This is the sha256: digest string.  Corresponds to Github API name
        # if the package is an untagged package
        self.digest = self._data["digest"]
        platform_data_os = self._data["platform"]["os"]
        platform_arch = self._data["platform"]["architecture"]
        platform_variant = self._data["platform"].get(
            "variant",
            "",
        )
        self.platform = f"{platform_data_os}/{platform_arch}{platform_variant}"


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

    # If given, the package is assumed to be a multi-arch manifest.  Cache packages are
    # not multi-arch, all other types are
    parser.add_argument(
        "--is-manifest",
        action="store_true",
        default=False,
        help="If provided, the package is assumed to be a multi-arch manifest following schema v2",
    )

    # Allows configuration of log level for debugging
    parser.add_argument(
        "--loglevel",
        default="info",
        help="Configures the logging level",
    )

    # Get the name of the package being processed this round
    parser.add_argument(
        "package",
        help="The package to process",
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

    # Find all branches named feature-*
    # Note: Only relevant to the main application, but simpler to
    # leave in for all packages
    with GithubBranchApi(gh_token) as branch_api:
        feature_branches = {}
        for branch in branch_api.get_branches(
            repo=repo,
        ):
            if branch.name.startswith("feature-"):
                logger.debug(f"Found feature branch {branch.name}")
                feature_branches[branch.name] = branch

        logger.info(f"Located {len(feature_branches)} feature branches")

    with GithubContainerRegistryApi(gh_token, repo_owner) as container_api:
        # Get the information about all versions of the given package
        all_package_versions: List[
            ContainerPackage
        ] = container_api.get_package_versions(args.package)

        all_pkgs_tags_to_version: Dict[str, ContainerPackage] = {}
        for pkg in all_package_versions:
            for tag in pkg.tags:
                all_pkgs_tags_to_version[tag] = pkg
        logger.info(
            f"Located {len(all_package_versions)} versions of package {args.package}",
        )

        # Filter to packages which are tagged with feature-*
        packages_tagged_feature: List[ContainerPackage] = []
        for package in all_package_versions:
            if package.tag_matches("feature-"):
                packages_tagged_feature.append(package)

        feature_pkgs_tags_to_versions: Dict[str, ContainerPackage] = {}
        for pkg in packages_tagged_feature:
            for tag in pkg.tags:
                feature_pkgs_tags_to_versions[tag] = pkg

        logger.info(
            f'Located {len(feature_pkgs_tags_to_versions)} versions of package {args.package} tagged "feature-"',
        )

        # All the feature tags minus all the feature branches leaves us feature tags
        # with no corresponding branch
        tags_to_delete = list(
            set(feature_pkgs_tags_to_versions.keys()) - set(feature_branches.keys()),
        )

        # All the tags minus the set of going to be deleted tags leaves us the
        # tags which will be kept around
        tags_to_keep = list(
            set(all_pkgs_tags_to_version.keys()) - set(tags_to_delete),
        )
        logger.info(
            f"Located {len(tags_to_delete)} versions of package {args.package} to delete",
        )

        # Delete certain package versions for which no branch existed
        for tag_to_delete in tags_to_delete:
            package_version_info = feature_pkgs_tags_to_versions[tag_to_delete]

            if args.delete:
                logger.info(
                    f"Deleting {tag_to_delete} (id {package_version_info.id})",
                )
                container_api.delete_package_version(
                    package_version_info,
                )

            else:
                logger.info(
                    f"Would delete {tag_to_delete} (id {package_version_info.id})",
                )

        # Deal with untagged package versions
        if args.untagged:

            logger.info("Handling untagged image packages")

            if not args.is_manifest:
                # If the package is not a multi-arch manifest, images without tags are safe to delete.
                # They are not referred to by anything.  This will leave all with at least 1 tag

                for package in all_package_versions:
                    if package.untagged:
                        if args.delete:
                            logger.info(
                                f"Deleting id {package.id} named {package.name}",
                            )
                            container_api.delete_package_version(
                                package,
                            )
                        else:
                            logger.info(
                                f"Would delete {package.name} (id {package.id})",
                            )
                    else:
                        logger.info(
                            f"Not deleting tag {package.tags[0]} of package {args.package}",
                        )
            else:

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
                    each of which appears as untagged image, but isn't really.

                    So from the list of untagged packages, remove those digests.  Once all tags which
                    are being kept are checked, the remaining untagged packages are actually untagged
                    with no referrals in a manifest to them.

                """

                # Simplify the untagged data, mapping name (which is a digest) to the version
                untagged_versions = {}
                for x in all_package_versions:
                    if x.untagged:
                        untagged_versions[x.name] = x

                skips = 0
                # Extra security to not delete on an unexpected error
                actually_delete = True

                # Parse manifests to locate digests pointed to
                for tag in sorted(tags_to_keep):
                    full_name = f"ghcr.io/{repo_owner}/{args.package}:{tag}"
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
                        for manifest_data in manifest_list["manifests"]:
                            manifest = DockerManifest2(manifest_data)

                            if manifest.digest in untagged_versions:
                                logger.debug(
                                    f"Skipping deletion of {manifest.digest}, referred to by {full_name} for {manifest.platform}",
                                )
                                del untagged_versions[manifest.digest]
                                skips += 1

                    except Exception as err:
                        actually_delete = False
                        logger.exception(err)

                logger.info(
                    f"Skipping deletion of {skips} packages referred to by a manifest",
                )

                # Step 3.3 - Delete the untagged and not pointed at packages
                logger.info(f"Deleting untagged packages of {args.package}")
                for to_delete_name in untagged_versions:
                    to_delete_version = untagged_versions[to_delete_name]

                    if args.delete and actually_delete:
                        logger.info(
                            f"Deleting id {to_delete_version.id} named {to_delete_version.name}",
                        )
                        container_api.delete_package_version(
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
