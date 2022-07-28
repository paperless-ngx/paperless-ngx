#!/usr/bin/env python3
import logging
from argparse import ArgumentError


def get_image_tag(
    repo_name: str,
    pkg_name: str,
    pkg_version: str,
) -> str:
    """
    Returns a string representing the normal image for a given package
    """
    return f"ghcr.io/{repo_name.lower()}/builder/{pkg_name}:{pkg_version}"


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
    return f"ghcr.io/{repo_name.lower()}/builder/cache/{pkg_name}:{pkg_version}"


def get_log_level(args) -> int:
    levels = {
        "critical": logging.CRITICAL,
        "error": logging.ERROR,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "info": logging.INFO,
        "debug": logging.DEBUG,
    }
    level = levels.get(args.loglevel.lower())
    if level is None:
        level = logging.INFO
    return level
