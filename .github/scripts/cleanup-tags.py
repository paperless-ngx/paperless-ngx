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
from typing import Optional

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
        # This is the sha256: digest string.  Corresponds to GitHub API name
        # if the package is an untagged package
        self.digest = self._data["digest"]
        platform_data_os = self._data["platform"]["os"]
        platform_arch = self._data["platform"]["architecture"]
        platform_variant = self._data["platform"].get(
            "variant",
            "",
        )
        self.platform = f"{platform_data_os}/{platform_arch}{platform_variant}"


class RegistryTagsCleaner:
    """
    This is the base class for the image registry cleaning.  Given a package
    name, it will keep all images which are tagged and all untagged images
    referred to by a manifest.  This results in only images which have been untagged
    and cannot be referenced except by their SHA in being removed.  None of these
    images should be referenced, so it is fine to delete them.
    """

    def __init__(
        self,
        package_name: str,
        repo_owner: str,
        repo_name: str,
        package_api: GithubContainerRegistryApi,
        branch_api: Optional[GithubBranchApi],
    ):
        self.actually_delete = False
        self.package_api = package_api
        self.branch_api = branch_api
        self.package_name = package_name
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.tags_to_delete: List[str] = []
        self.tags_to_keep: List[str] = []

        # Get the information about all versions of the given package
        # These are active, not deleted, the default returned from the API
        self.all_package_versions = self.package_api.get_active_package_versions(
            self.package_name,
        )

        # Get a mapping from a tag like "1.7.0" or "feature-xyz" to the ContainerPackage
        # tagged with it.  It makes certain lookups easy
        self.all_pkgs_tags_to_version: Dict[str, ContainerPackage] = {}
        for pkg in self.all_package_versions:
            for tag in pkg.tags:
                self.all_pkgs_tags_to_version[tag] = pkg
        logger.info(
            f"Located {len(self.all_package_versions)} versions of package {self.package_name}",
        )

        self.decide_what_tags_to_keep()

    def clean(self):
        """
        This method will delete image versions, based on the selected tags to delete
        """
        for tag_to_delete in self.tags_to_delete:
            package_version_info = self.all_pkgs_tags_to_version[tag_to_delete]

            if self.actually_delete:
                logger.info(
                    f"Deleting {tag_to_delete} (id {package_version_info.id})",
                )
                self.package_api.delete_package_version(
                    package_version_info,
                )

            else:
                logger.info(
                    f"Would delete {tag_to_delete} (id {package_version_info.id})",
                )
        else:
            logger.info("No tags to delete")

    def clean_untagged(self, is_manifest_image: bool):
        """
        This method will delete untagged images, that is those which are not named.  It
        handles if the image tag is actually a manifest, which points to images that look otherwise
        untagged.
        """

        def _clean_untagged_manifest():
            """

            Handles the deletion of untagged images, but where the package is a manifest, ie a multi
            arch image, which means some "untagged" images need to exist still.

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
            # At the moment, these are the images which APPEAR untagged.
            untagged_versions = {}
            for x in self.all_package_versions:
                if x.untagged:
                    untagged_versions[x.name] = x

            skips = 0

            # Parse manifests to locate digests pointed to
            for tag in sorted(self.tags_to_keep):
                full_name = f"ghcr.io/{self.repo_owner}/{self.package_name}:{tag}"
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
                            logger.info(
                                f"Skipping deletion of {manifest.digest},"
                                f" referred to by {full_name}"
                                f" for {manifest.platform}",
                            )
                            del untagged_versions[manifest.digest]
                            skips += 1

                except Exception as err:
                    self.actually_delete = False
                    logger.exception(err)
                    return

            logger.info(
                f"Skipping deletion of {skips} packages referred to by a manifest",
            )

            # Delete the untagged and not pointed at packages
            logger.info(f"Deleting untagged packages of {self.package_name}")
            for to_delete_name in untagged_versions:
                to_delete_version = untagged_versions[to_delete_name]

                if self.actually_delete:
                    logger.info(
                        f"Deleting id {to_delete_version.id} named {to_delete_version.name}",
                    )
                    self.package_api.delete_package_version(
                        to_delete_version,
                    )
                else:
                    logger.info(
                        f"Would delete {to_delete_name} (id {to_delete_version.id})",
                    )

        def _clean_untagged_non_manifest():
            """
            If the package is not a multi-arch manifest, images without tags are safe to delete.
            """

            for package in self.all_package_versions:
                if package.untagged:
                    if self.actually_delete:
                        logger.info(
                            f"Deleting id {package.id} named {package.name}",
                        )
                        self.package_api.delete_package_version(
                            package,
                        )
                    else:
                        logger.info(
                            f"Would delete {package.name} (id {package.id})",
                        )
                else:
                    logger.info(
                        f"Not deleting tag {package.tags[0]} of package {self.package_name}",
                    )

        logger.info("Beginning untagged image cleaning")

        if is_manifest_image:
            _clean_untagged_manifest()
        else:
            _clean_untagged_non_manifest()

    def decide_what_tags_to_keep(self):
        """
        This method holds the logic to delete what tags to keep and there fore
        what tags to delete.

        By default, any image with at least 1 tag will be kept
        """
        # By default, keep anything which is tagged
        self.tags_to_keep = list(set(self.all_pkgs_tags_to_version.keys()))


class MainImageTagsCleaner(RegistryTagsCleaner):
    def decide_what_tags_to_keep(self):
        """
        Overrides the default logic for deciding what images to keep.  Images tagged as "feature-"
        will be removed, if the corresponding branch no longer exists.
        """

        # Default to everything gets kept still
        super().decide_what_tags_to_keep()

        # Locate the feature branches
        feature_branches = {}
        for branch in self.branch_api.get_branches(
            repo=self.repo_name,
        ):
            if branch.name.startswith("feature-"):
                logger.debug(f"Found feature branch {branch.name}")
                feature_branches[branch.name] = branch

        logger.info(f"Located {len(feature_branches)} feature branches")

        if not len(feature_branches):
            # Our work here is done, delete nothing
            return

        # Filter to packages which are tagged with feature-*
        packages_tagged_feature: List[ContainerPackage] = []
        for package in self.all_package_versions:
            if package.tag_matches("feature-"):
                packages_tagged_feature.append(package)

        # Map tags like "feature-xyz" to a ContainerPackage
        feature_pkgs_tags_to_versions: Dict[str, ContainerPackage] = {}
        for pkg in packages_tagged_feature:
            for tag in pkg.tags:
                feature_pkgs_tags_to_versions[tag] = pkg

        logger.info(
            f'Located {len(feature_pkgs_tags_to_versions)} versions of package {self.package_name} tagged "feature-"',
        )

        # All the feature tags minus all the feature branches leaves us feature tags
        # with no corresponding branch
        self.tags_to_delete = list(
            set(feature_pkgs_tags_to_versions.keys()) - set(feature_branches.keys()),
        )

        # All the tags minus the set of going to be deleted tags leaves us the
        # tags which will be kept around
        self.tags_to_keep = list(
            set(self.all_pkgs_tags_to_version.keys()) - set(self.tags_to_delete),
        )
        logger.info(
            f"Located {len(self.tags_to_delete)} versions of package {self.package_name} to delete",
        )


class LibraryTagsCleaner(RegistryTagsCleaner):
    """
    Exists for the off change that someday, the installer library images
    will need their own logic
    """

    pass


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
        with GithubContainerRegistryApi(gh_token, repo_owner) as container_api:
            if args.package in {"paperless-ngx", "paperless-ngx/builder/cache/app"}:
                cleaner = MainImageTagsCleaner(
                    args.package,
                    repo_owner,
                    repo,
                    container_api,
                    branch_api,
                )
            else:
                cleaner = LibraryTagsCleaner(
                    args.package,
                    repo_owner,
                    repo,
                    container_api,
                    None,
                )

            # Set if actually doing a delete vs dry run
            cleaner.actually_delete = args.delete

            # Clean images with tags
            cleaner.clean()

            # Clean images which are untagged
            cleaner.clean_untagged(args.is_manifest)


if __name__ == "__main__":
    _main()
