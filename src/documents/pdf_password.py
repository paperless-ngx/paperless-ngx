"""
Utility functions for handling password-protected PDFs.

This module provides helpers to unlock (remove encryption from) PDFs either
in-place or by writing an unlocked temporary copy. It relies on `pikepdf` and
only applies to PDF files.
"""
import logging
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

import pikepdf

logger = logging.getLogger("paperless.pdf_password")


def remove_pdf_password(file_path: Path, password: str) -> Path | None:
    """
    Attempt to remove password protection from a PDF file.

    Args:
        file_path: Path to the password-protected PDF.
        password: Password to unlock the PDF.

    Returns:
        Path to a new temporary, unlocked PDF file, or None if unlocking
        fails. The original input file is not modified.
    """
    if not file_path.exists():
        logger.error(f"File does not exist: {file_path}")
        return None

    try:
        # Open the password-protected PDF
        with pikepdf.open(file_path, password=password) as pdf:
            # Create a temporary file to save the unlocked PDF
            temp_file = NamedTemporaryFile(
                delete=False,
                suffix=".pdf",
                prefix="unlocked_",
            )
            temp_path = Path(temp_file.name)
            temp_file.close()

            # Save without encryption
            pdf.save(temp_path, encryption=False)

            logger.info(f"Successfully removed password from PDF: {file_path.name}")
            return temp_path

    except pikepdf.PasswordError:
        logger.warning(
            f"Incorrect password provided for PDF: {file_path.name}",
        )
        return None
    except Exception as e:
        logger.error(
            f"Error removing password from PDF {file_path.name}: {e}",
        )
        return None


def unlock_pdf_in_place(file_path: Path, password: str) -> bool:
    """
    Unlock a password-protected PDF in place by saving it without encryption.
    The original file is replaced with the unlocked version.

    Args:
        file_path: Path to the PDF.
        password: Password to unlock the PDF.

    Returns:
        True on success, False otherwise.
    """
    if not file_path.exists():
        logger.error(f"File does not exist, cannot unlock: {file_path}")
        return False

    if file_path.suffix.lower() != ".pdf":
        logger.warning(f"File is not a PDF, skipping unlock: {file_path.name}")
        return False

    try:
        # Open with password
        with pikepdf.open(file_path, password=password, allow_overwriting_input=True) as pdf:
            # Save without encryption, overwriting the original
            pdf.save(file_path, encryption=False)
            logger.info(f"Successfully unlocked PDF in place: {file_path.name}")
            return True

    except pikepdf.PasswordError:
        logger.warning(f"Incorrect password for PDF: {file_path.name}")
        return False
    except Exception as e:
        logger.error(f"Failed to unlock PDF {file_path.name}: {e}", exc_info=True)
        return False


def lock_pdf_in_place(file_path: Path, password: str) -> bool:
    """
    Encrypt a PDF in place with the provided password.
    The original file is replaced with the encrypted version.

    Args:
        file_path: Path to the PDF.
        password: Password to set for the encrypted PDF (used as both
            user and owner password).

    Returns:
        True on success, False otherwise.
    """
    if not file_path.exists():
        logger.error(f"File does not exist, cannot lock: {file_path}")
        return False

    if file_path.suffix.lower() != ".pdf":
        logger.warning(f"File is not a PDF, skipping lock: {file_path.name}")
        return False

    try:
        # Open with password
        with pikepdf.open(file_path, password=password, allow_overwriting_input=True) as pdf:

            # Save with encryption, overwriting the original
            logger.debug(f"Saving encrypted PDF: {file_path}")

            no_extracting = pikepdf.Permissions(extract=False)
            pdf.save(file_path, encryption=pikepdf.Encryption(
                user=password, owner=password, allow=no_extracting
            ))
            return True

    except pikepdf.PasswordError:
        logger.warning(f"Incorrect password provided for PDF: {file_path.name}")
        return False
    except Exception as e:
        logger.error(f"Failed to lock PDF {file_path.name}: {e}", exc_info=True)
        return False
