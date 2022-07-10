#!/usr/bin/env python3


def get_image_tag(
    repo_name: str,
    pkg_name: str,
    pkg_version: str,
) -> str:
    """
    Returns a string representing the normal image for a given package
    """
    return f"ghcr.io/{repo_name}/builder/{pkg_name}:{pkg_version}"


def get_cache_image_tag(
    repo_name: str,
    pkg_name: str,
    pkg_version: str,
    branch_name: str,
) -> str:
    """
    Returns a string representing the expected image cache tag for a given package

    Registry type caching is utilized for the builder images, to allow fast
    rebuilds, generally almost instant for the same version
    """
    return f"ghcr.io/{repo_name}/builder/cache/{pkg_name}:{pkg_version}"
