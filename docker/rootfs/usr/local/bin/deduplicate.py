#!/usr/bin/env python3
"""
File deduplication script that replaces identical files with symlinks.
Uses SHA256 hashing to identify duplicate files.
"""

import hashlib
from collections import defaultdict
from pathlib import Path

import click
import humanize


def calculate_sha256(filepath: Path) -> str | None:
    sha256_hash = hashlib.sha256()
    try:
        with filepath.open("rb") as f:
            # Read file in chunks to handle large files efficiently
            while chunk := f.read(65536):  # 64KB chunks
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except OSError as e:
        click.echo(f"Error reading {filepath}: {e}", err=True)
        return None


def find_duplicate_files(directory: Path) -> dict[str, list[Path]]:
    """
    Recursively scan directory and group files by their SHA256 hash.
    Returns a dictionary mapping hash -> list of file paths.
    """
    hash_to_files: dict[str, list[Path]] = defaultdict(list)

    for filepath in directory.rglob("*"):
        # Skip symlinks
        if filepath.is_symlink():
            continue

        # Skip if not a regular file
        if not filepath.is_file():
            continue

        file_hash = calculate_sha256(filepath)
        if file_hash:
            hash_to_files[file_hash].append(filepath)

    # Filter to only return hashes with duplicates
    return {h: files for h, files in hash_to_files.items() if len(files) > 1}


def replace_with_symlinks(
    duplicate_groups: dict[str, list[Path]],
    *,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Replace duplicate files with symlinks to the first occurrence.
    Returns (number_of_files_replaced, space_saved_in_bytes).
    """
    total_duplicates = 0
    space_saved = 0

    for file_hash, file_list in duplicate_groups.items():
        # Keep the first file as the original, replace others with symlinks
        original_file = file_list[0]
        duplicates = file_list[1:]

        click.echo(f"Found {len(duplicates)} duplicate(s) of: {original_file}")

        for duplicate in duplicates:
            try:
                # Get file size before deletion
                file_size = duplicate.stat().st_size

                if dry_run:
                    click.echo(f"  [DRY RUN] Would replace: {duplicate}")
                else:
                    # Remove the duplicate file
                    duplicate.unlink()

                    # Create relative symlink if possible, otherwise absolute
                    try:
                        # Try to create a relative symlink
                        rel_path = original_file.relative_to(duplicate.parent)
                        duplicate.symlink_to(rel_path)
                        click.echo(f"  Replaced: {duplicate} -> {rel_path}")
                    except ValueError:
                        # Fall back to absolute path
                        duplicate.symlink_to(original_file.resolve())
                        click.echo(f"  Replaced: {duplicate} -> {original_file}")

                    space_saved += file_size

                total_duplicates += 1

            except OSError as e:
                click.echo(f"  Error replacing {duplicate}: {e}", err=True)

    return total_duplicates, space_saved


@click.command()
@click.argument(
    "directory",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        path_type=Path,
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes",
)
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
def deduplicate(directory: Path, *, dry_run: bool, verbose: bool) -> None:
    """
    Recursively search DIRECTORY for identical files and replace them with symlinks.

    Uses SHA256 hashing to identify duplicate files. The first occurrence of each
    unique file is kept, and all duplicates are replaced with symlinks pointing to it.
    """
    directory = directory.resolve()

    click.echo(f"Scanning directory: {directory}")
    if dry_run:
        click.echo("Running in DRY RUN mode - no changes will be made")

    # Find all duplicate files
    click.echo("Calculating file hashes...")
    duplicate_groups = find_duplicate_files(directory)

    if not duplicate_groups:
        click.echo("No duplicate files found!")
        return

    total_files = sum(len(files) - 1 for files in duplicate_groups.values())
    click.echo(
        f"Found {len(duplicate_groups)} group(s) of duplicates "
        f"({total_files} files to deduplicate)",
    )

    if verbose:
        for file_hash, files in duplicate_groups.items():
            click.echo(f"Hash: {file_hash}")
            for f in files:
                click.echo(f"  - {f}")

    # Replace duplicates with symlinks
    click.echo("Processing duplicates...")
    num_replaced, space_saved = replace_with_symlinks(duplicate_groups, dry_run=dry_run)

    # Summary
    click.echo(
        f"{'Would replace' if dry_run else 'Replaced'} "
        f"{num_replaced} duplicate file(s)",
    )
    if not dry_run:
        click.echo(f"Space saved: {humanize.naturalsize(space_saved, binary=True)}")


if __name__ == "__main__":
    deduplicate()
