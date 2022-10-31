#!/usr/bin/env python3
"""
This module contains some useful classes for interacting with the Github API.
The full documentation for the API can be found here: https://docs.github.com/en/rest

Mostly, this focusses on two areas, repo branches and repo packages, as the use case
is cleaning up container images which are no longer referred to.

"""
import functools
import logging
import re
import urllib.parse
from typing import Dict
from typing import List
from typing import Optional

import httpx

logger = logging.getLogger("github-api")


class _GithubApiBase:
    """
    A base class for interacting with the Github API.  It
    will handle the session and setting authorization headers.
    """

    def __init__(self, token: str) -> None:
        self._token = token
        self._client: Optional[httpx.Client] = None

    def __enter__(self) -> "_GithubApiBase":
        """
        Sets up the required headers for auth and response
        type from the API
        """
        self._client = httpx.Client()
        self._client.headers.update(
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
        if "Accept" in self._client.headers:
            del self._client.headers["Accept"]
        if "Authorization" in self._client.headers:
            del self._client.headers["Authorization"]

        # Close the session as well
        self._client.close()
        self._client = None

    def _read_all_pages(self, endpoint):
        """
        Helper function to read all pages of an endpoint, utilizing the
        next.url until exhausted.  Assumes the endpoint returns a list
        """
        internal_data = []

        while True:
            resp = self._client.get(endpoint)
            if resp.status_code == 200:
                internal_data += resp.json()
                if "next" in resp.links:
                    endpoint = resp.links["next"]["url"]
                else:
                    logger.debug("Exiting pagination loop")
                    break
            else:
                logger.warning(f"Request to {endpoint} return HTTP {resp.status_code}")
                resp.raise_for_status()

        return internal_data


class _EndpointResponse:
    """
    For all endpoint JSON responses, store the full
    response data, for ease of extending later, if need be.
    """

    def __init__(self, data: Dict) -> None:
        self._data = data


class GithubBranch(_EndpointResponse):
    """
    Simple wrapper for a repository branch, only extracts name information
    for now.
    """

    def __init__(self, data: Dict) -> None:
        super().__init__(data)
        self.name = self._data["name"]


class GithubBranchApi(_GithubApiBase):
    """
    Wrapper around branch API.

    See https://docs.github.com/en/rest/branches/branches

    """

    def __init__(self, token: str) -> None:
        super().__init__(token)

        self._ENDPOINT = "https://api.github.com/repos/{REPO}/branches"

    def get_branches(self, repo: str) -> List[GithubBranch]:
        """
        Returns all current branches of the given repository owned by the given
        owner or organization.
        """
        # The environment GITHUB_REPOSITORY already contains the owner in the correct location
        endpoint = self._ENDPOINT.format(REPO=repo)
        internal_data = self._read_all_pages(endpoint)
        return [GithubBranch(branch) for branch in internal_data]


class ContainerPackage(_EndpointResponse):
    """
    Data class wrapping the JSON response from the package related
    endpoints
    """

    def __init__(self, data: Dict):
        super().__init__(data)
        # This is a numerical ID, required for interactions with this
        # specific package, including deletion of it or restoration
        self.id: int = self._data["id"]

        # A string name.  This might be an actual name or it could be a
        # digest string like "sha256:"
        self.name: str = self._data["name"]

        # URL to the package, including its ID, can be used for deletion
        # or restoration without needing to build up a URL ourselves
        self.url: str = self._data["url"]

        # The list of tags applied to this image. Maybe an empty list
        self.tags: List[str] = self._data["metadata"]["container"]["tags"]

    @functools.cached_property
    def untagged(self) -> bool:
        """
        Returns True if the image has no tags applied to it, False otherwise
        """
        return len(self.tags) == 0

    @functools.cache
    def tag_matches(self, pattern: str) -> bool:
        """
        Returns True if the image has at least one tag which matches the given regex,
        False otherwise
        """
        for tag in self.tags:
            if re.match(pattern, tag) is not None:
                return True
        return False

    def __repr__(self):
        return f"Package {self.name}"


class GithubContainerRegistryApi(_GithubApiBase):
    """
    Class wrapper to deal with the Github packages API.  This class only deals with
    container type packages, the only type published by paperless-ngx.
    """

    def __init__(self, token: str, owner_or_org: str) -> None:
        super().__init__(token)
        self._owner_or_org = owner_or_org
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
        self._PACKAGE_VERSION_RESTORE_ENDPOINT = (
            f"{self._PACKAGE_VERSION_DELETE_ENDPOINT}/restore"
        )

    def get_active_package_versions(
        self,
        package_name: str,
    ) -> List[ContainerPackage]:
        """
        Returns all the versions of a given package (container images) from
        the API
        """

        package_type: str = "container"
        # Need to quote this for slashes in the name
        package_name = urllib.parse.quote(package_name, safe="")

        endpoint = self._PACKAGES_VERSIONS_ENDPOINT.format(
            ORG=self._owner_or_org,
            PACKAGE_TYPE=package_type,
            PACKAGE_NAME=package_name,
        )

        pkgs = []

        for data in self._read_all_pages(endpoint):
            pkgs.append(ContainerPackage(data))

        return pkgs

    def get_deleted_package_versions(
        self,
        package_name: str,
    ) -> List[ContainerPackage]:
        package_type: str = "container"
        # Need to quote this for slashes in the name
        package_name = urllib.parse.quote(package_name, safe="")

        endpoint = (
            self._PACKAGES_VERSIONS_ENDPOINT.format(
                ORG=self._owner_or_org,
                PACKAGE_TYPE=package_type,
                PACKAGE_NAME=package_name,
            )
            + "?state=deleted"
        )

        pkgs = []

        for data in self._read_all_pages(endpoint):
            pkgs.append(ContainerPackage(data))

        return pkgs

    def delete_package_version(self, package_data: ContainerPackage):
        """
        Deletes the given package version from the GHCR
        """
        resp = self._client.delete(package_data.url)
        if resp.status_code != 204:
            logger.warning(
                f"Request to delete {package_data.url} returned HTTP {resp.status_code}",
            )

    def restore_package_version(
        self,
        package_name: str,
        package_data: ContainerPackage,
    ):
        package_type: str = "container"
        endpoint = self._PACKAGE_VERSION_RESTORE_ENDPOINT.format(
            ORG=self._owner_or_org,
            PACKAGE_TYPE=package_type,
            PACKAGE_NAME=package_name,
            PACKAGE_VERSION_ID=package_data.id,
        )

        resp = self._client.post(endpoint)
        if resp.status_code != 204:
            logger.warning(
                f"Request to delete {endpoint} returned HTTP {resp.status_code}",
            )
