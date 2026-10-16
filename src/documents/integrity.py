"""Versioned stdin/stdout bridge to the read-only Go integrity scanner."""

import json
import subprocess
from typing import TypedDict

from django.conf import settings


class IntegrityScanError(Exception):
    """The scanner could not complete a trustworthy scan."""


class ExpectedFile(TypedDict):
    document_id: int
    kind: str
    path: str
    checksum: str


class Manifest(TypedDict):
    version: int
    media_root: str
    checksum_algorithm: str
    files: list[ExpectedFile]
    ignored_filenames: list[str]
    excluded_paths: list[str]


class Finding(TypedDict):
    code: str
    file_index: int | None
    path: str
    detail: str
    actual_checksum: str


def _validate_response(output: bytes, manifest: Manifest) -> list[Finding]:
    try:
        result = json.loads(output.decode("utf-8"))
        if not isinstance(result, dict) or set(result) != {
            "version",
            "complete",
            "checked_files",
            "findings",
        }:
            raise ValueError("invalid response fields")
        if type(result["version"]) is not int or result["version"] != 1:
            raise ValueError("unsupported response version")
        if result["complete"] is not True:
            raise ValueError("incomplete scan")
        if type(result["checked_files"]) is not int or result["checked_files"] != len(
            manifest["files"],
        ):
            raise ValueError("incomplete expected-file checks")
        if not isinstance(result["findings"], list):
            raise ValueError("invalid findings")
        findings: list[Finding] = []
        for finding in result["findings"]:
            if not isinstance(finding, dict) or set(finding) != {
                "code",
                "file_index",
                "path",
                "detail",
                "actual_checksum",
            }:
                raise ValueError("invalid finding fields")
            if any(
                not isinstance(finding[key], str)
                for key in ("code", "path", "detail", "actual_checksum")
            ):
                raise ValueError("invalid finding strings")
            index = finding["file_index"]
            code = finding["code"]
            if index is None:
                if code not in {"orphan", "unsafe_path"}:
                    raise ValueError("invalid global finding")
            elif type(index) is not int or not 0 <= index < len(manifest["files"]):
                raise ValueError("invalid file index")
            else:
                expected = manifest["files"][index]
                if code not in {
                    "missing",
                    "unreadable",
                    "checksum_mismatch",
                    "unsafe_path",
                }:
                    raise ValueError("invalid file finding")
                if finding["path"] != expected["path"]:
                    raise ValueError("finding path does not match manifest")
                if code == "checksum_mismatch" and (
                    expected["kind"] == "thumbnail"
                    or len(finding["actual_checksum"]) != 64
                    or any(
                        c not in "0123456789abcdef" for c in finding["actual_checksum"]
                    )
                    or finding["actual_checksum"] == expected["checksum"]
                ):
                    raise ValueError("invalid checksum finding")
            findings.append(
                Finding(
                    code=code,
                    file_index=index,
                    path=finding["path"],
                    detail=finding["detail"],
                    actual_checksum=finding["actual_checksum"],
                ),
            )
        return findings
    except (ValueError, KeyError, TypeError) as e:
        raise IntegrityScanError(f"Invalid integrity scanner response: {e}") from e


def scan_files(manifest: Manifest) -> list[Finding]:
    """Run the mandatory scanner, killing/reaping it on timeout or interruption."""
    try:
        process = subprocess.Popen(
            [str(settings.INTEGRITY_SCANNER_BINARY)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as e:
        raise IntegrityScanError(
            f"Cannot start integrity scanner {settings.INTEGRITY_SCANNER_BINARY}: {e}. "
            "Build/install native/integrity or set PAPERLESS_INTEGRITY_SCANNER_BINARY.",
        ) from e
    try:
        output, stderr = process.communicate(
            json.dumps(manifest, ensure_ascii=True).encode("utf-8"),
            timeout=settings.INTEGRITY_SCANNER_TIMEOUT,
        )
    except BaseException as e:
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
        if isinstance(e, subprocess.TimeoutExpired):
            raise IntegrityScanError(
                "Integrity scanner timed out; scan incomplete.",
            ) from e
        raise
    if process.returncode != 0:
        raise IntegrityScanError(
            f"Integrity scanner failed (exit {process.returncode}); scan incomplete: "
            f"{stderr.decode('utf-8', errors='replace').strip() or output.decode('utf-8', errors='replace').strip()}",
        )
    return _validate_response(output, manifest)
