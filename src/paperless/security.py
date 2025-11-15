"""
Security utilities for IntelliDocs-ngx.

Provides enhanced security features including file validation,
malicious content detection, and security checks.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import magic

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger("paperless.security")


# Lista explícita de tipos MIME permitidos
ALLOWED_MIME_TYPES = {
    # Documentos
    'application/pdf',
    'application/vnd.oasis.opendocument.text',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.oasis.opendocument.spreadsheet',
    'application/vnd.oasis.opendocument.presentation',
    'application/rtf',
    'text/rtf',

    # Imágenes
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/tiff',
    'image/bmp',
    'image/webp',

    # Texto
    'text/plain',
    'text/html',
    'text/csv',
    'text/markdown',
}

# Maximum file size (100MB by default)
# Can be overridden by settings.MAX_UPLOAD_SIZE
try:
    from django.conf import settings
    MAX_FILE_SIZE = getattr(settings, 'MAX_UPLOAD_SIZE', 100 * 1024 * 1024)  # 100MB por defecto
except ImportError:
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes

# Dangerous file extensions that should never be allowed
DANGEROUS_EXTENSIONS = {
    ".exe",
    ".dll",
    ".bat",
    ".cmd",
    ".com",
    ".scr",
    ".vbs",
    ".js",
    ".jar",
    ".msi",
    ".app",
    ".deb",
    ".rpm",
}

# Patterns that might indicate malicious content
# SECURITY: Refined patterns to reduce false positives while maintaining protection
MALICIOUS_PATTERNS = [
    # JavaScript malicioso en PDFs (excluye formularios legítimos)
    # Nota: No usar rb"/JavaScript" directamente - demasiado amplio
    rb"/Launch",  # Launch actions son peligrosas
    rb"/OpenAction(?!.*?/AcroForm)",  # OpenAction sin formularios

    # Código ejecutable embebido (archivo)
    rb"/EmbeddedFile.*?\.exe",
    rb"/EmbeddedFile.*?\.bat",
    rb"/EmbeddedFile.*?\.cmd",
    rb"/EmbeddedFile.*?\.sh",
    rb"/EmbeddedFile.*?\.vbs",
    rb"/EmbeddedFile.*?\.ps1",

    # Ejecutables (headers de binarios)
    rb"MZ\x90\x00",  # PE executable header (Windows)
    rb"\x7fELF",  # ELF executable header (Linux)

    # SubmitForm a dominios externos no confiables
    rb"/SubmitForm.*?https?://(?!localhost|127\.0\.0\.1|trusted-domain\.com)",
]

# Whitelist para JavaScript legítimo en PDFs (formularios Adobe)
ALLOWED_JS_PATTERNS = [
    rb"/AcroForm",  # Formularios Adobe
    rb"/Annot.*?/Widget",  # Widgets de formulario
    rb"/Fields\[",  # Campos de formulario
]


class FileValidationError(Exception):
    """Raised when file validation fails."""

    pass


def has_whitelisted_javascript(content: bytes) -> bool:
    """
    Check if PDF has whitelisted JavaScript (legitimate forms).

    Args:
        content: File content to check

    Returns:
        bool: True if PDF contains legitimate JavaScript (forms), False otherwise
    """
    return any(re.search(pattern, content) for pattern in ALLOWED_JS_PATTERNS)


def validate_mime_type(mime_type: str) -> None:
    """
    Validate MIME type against whitelist.

    Args:
        mime_type: MIME type to validate

    Raises:
        FileValidationError: If MIME type is not allowed
    """
    if mime_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError(
            f"MIME type '{mime_type}' is not allowed. "
            f"Allowed types: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
        )


def validate_uploaded_file(uploaded_file: UploadedFile) -> dict:
    """
    Validate an uploaded file for security.
    
    Performs multiple checks:
    1. File size validation
    2. MIME type validation
    3. File extension validation
    4. Content validation (checks for malicious patterns)
    
    Args:
        uploaded_file: Django UploadedFile object
        
    Returns:
        dict: Validation result with 'valid' boolean and 'mime_type'
        
    Raises:
        FileValidationError: If validation fails
    """
    # Check file size
    if uploaded_file.size > MAX_FILE_SIZE:
        raise FileValidationError(
            f"File size ({uploaded_file.size} bytes) exceeds maximum allowed "
            f"size ({MAX_FILE_SIZE} bytes)",
        )

    # Check file extension
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    if file_ext in DANGEROUS_EXTENSIONS:
        raise FileValidationError(
            f"File extension '{file_ext}' is not allowed for security reasons",
        )

    # Read file content for validation
    uploaded_file.seek(0)
    content = uploaded_file.read(8192)  # Read first 8KB for validation
    uploaded_file.seek(0)  # Reset file pointer

    # Detect MIME type from content (more reliable than extension)
    mime_type = magic.from_buffer(content, mime=True)

    # Validate MIME type using strict whitelist
    validate_mime_type(mime_type)

    # Check for malicious patterns
    check_malicious_content(content)

    logger.info(
        f"File validated successfully: {uploaded_file.name} "
        f"(size: {uploaded_file.size}, mime: {mime_type})",
    )

    return {
        "valid": True,
        "mime_type": mime_type,
        "size": uploaded_file.size,
    }


def validate_file_path(file_path: str | Path) -> dict:
    """
    Validate a file on disk for security.
    
    Args:
        file_path: Path to the file
        
    Returns:
        dict: Validation result
        
    Raises:
        FileValidationError: If validation fails
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileValidationError(f"File does not exist: {file_path}")

    if not file_path.is_file():
        raise FileValidationError(f"Path is not a file: {file_path}")

    # Check file size
    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        raise FileValidationError(
            f"File size ({file_size} bytes) exceeds maximum allowed "
            f"size ({MAX_FILE_SIZE} bytes)",
        )

    # Check extension
    file_ext = file_path.suffix.lower()
    if file_ext in DANGEROUS_EXTENSIONS:
        raise FileValidationError(
            f"File extension '{file_ext}' is not allowed for security reasons",
        )

    # Detect MIME type
    mime_type = magic.from_file(str(file_path), mime=True)

    # Validate MIME type using strict whitelist
    validate_mime_type(mime_type)

    # Check for malicious content
    with open(file_path, "rb") as f:
        content = f.read(8192)  # Read first 8KB
        check_malicious_content(content)

    logger.info(
        f"File validated successfully: {file_path.name} "
        f"(size: {file_size}, mime: {mime_type})",
    )

    return {
        "valid": True,
        "mime_type": mime_type,
        "size": file_size,
    }


def check_malicious_content(content: bytes) -> None:
    """
    Check file content for potentially malicious patterns.

    SECURITY: Enhanced validation with whitelist support
    - Verifica patrones maliciosos específicos
    - Permite JavaScript legítimo (formularios PDF)
    - Reduce falsos positivos manteniendo seguridad

    Args:
        content: File content to check (first few KB)

    Raises:
        FileValidationError: If malicious patterns are detected
    """
    # Primero verificar si tiene JavaScript (antes de rechazar por patrones)
    has_javascript = rb"/JavaScript" in content or rb"/JS" in content

    if has_javascript:
        # Si tiene JavaScript, verificar si es legítimo (formularios)
        if not has_whitelisted_javascript(content):
            # JavaScript no permitido - verificar si es malicioso
            # Solo rechazar si no es un formulario legítimo
            raise FileValidationError(
                "File contains potentially malicious JavaScript and has been rejected. "
                "PDF forms with AcroForm are allowed.",
            )

    # Verificar otros patrones maliciosos
    for pattern in MALICIOUS_PATTERNS:
        if re.search(pattern, content):
            raise FileValidationError(
                "File contains potentially malicious content and has been rejected",
            )


def calculate_file_hash(file_path: str | Path, algorithm: str = "sha256") -> str:
    """
    Calculate cryptographic hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use (default: sha256)
        
    Returns:
        str: Hexadecimal hash string
    """
    hash_obj = hashlib.new(algorithm)

    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files efficiently
        for chunk in iter(lambda: f.read(8192), b""):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Remove any path components
    filename = os.path.basename(filename)

    # Remove or replace dangerous characters
    # Keep alphanumeric, dots, dashes, underscores, and spaces
    sanitized = re.sub(r"[^\w\s.-]", "_", filename)

    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(". ")

    # Ensure filename is not empty
    if not sanitized:
        sanitized = "unnamed_file"

    # Limit length
    max_length = 255
    if len(sanitized) > max_length:
        name, ext = os.path.splitext(sanitized)
        name = name[: max_length - len(ext) - 1]
        sanitized = name + ext

    return sanitized


def is_safe_redirect_url(url: str, allowed_hosts: list[str]) -> bool:
    """
    Check if a redirect URL is safe (no open redirect vulnerability).
    
    Args:
        url: URL to check
        allowed_hosts: List of allowed hostnames
        
    Returns:
        bool: True if URL is safe
    """
    # Relative URLs are safe
    if url.startswith("/") and not url.startswith("//"):
        return True

    # Check if URL hostname is in allowed hosts
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False
        if parsed.hostname in allowed_hosts:
            return True
    except (ValueError, AttributeError):
        return False

    return False
