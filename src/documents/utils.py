
import logging
import os
import re
import shutil
import subprocess
import tempfile
from os import utime
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import run
from typing import Optional
from typing import Union

import PyPDF2
import pathvalidate
from PIL import Image
from django.conf import settings


def _coerce_to_path(
    source: Union[Path, str],
    dest: Union[Path, str],
) -> tuple[Path, Path]:
    return Path(source).resolve(), Path(dest).resolve()


def copy_basic_file_stats(source: Union[Path, str], dest: Union[Path, str]) -> None:
    """
    Copies only the m_time and a_time attributes from source to destination.
    Both are expected to exist.

    The extended attribute copy does weird things with SELinux and files
    copied from temporary directories and copystat doesn't allow disabling
    these copies
    """
    source, dest = _coerce_to_path(source, dest)
    src_stat = source.stat()
    utime(dest, ns=(src_stat.st_atime_ns, src_stat.st_mtime_ns))


def copy_file_with_basic_stats(
    source: Union[Path, str],
    dest: Union[Path, str],
) -> None:
    """
    A sort of simpler copy2 that doesn't copy extended file attributes,
    only the access time and modified times from source to dest.

    The extended attribute copy does weird things with SELinux and files
    copied from temporary directories.
    """
    source, dest = _coerce_to_path(source, dest)

    shutil.copy(source, dest)
    copy_basic_file_stats(source, dest)


def maybe_override_pixel_limit() -> None:
    """
    Maybe overrides the PIL limit on pixel count, if configured to allow it
    """
    limit: Optional[Union[float, int]] = settings.MAX_IMAGE_PIXELS
    if limit is not None and limit >= 0:
        pixel_count = limit
        if pixel_count == 0:
            pixel_count = None
        Image.MAX_IMAGE_PIXELS = pixel_count


def run_subprocess(
    arguments: list[str],
    env: Optional[dict[str, str]] = None,
    logger: Optional[logging.Logger] = None,
    *,
    check_exit_code: bool = True,
    log_stdout: bool = True,
    log_stderr: bool = True,
) -> CompletedProcess:
    """
    Runs a subprocess and logs its output, checking return code if requested
    """

    proc_name = arguments[0]

    completed_proc = run(args=arguments, env=env, capture_output=True, check=False)

    if logger:
        logger.info(f"{proc_name} exited {completed_proc.returncode}")

    if log_stdout and logger and completed_proc.stdout:
        stdout_str = (
            completed_proc.stdout.decode("utf8", errors="ignore")
            .strip()
            .split(
                "\n",
            )
        )
        logger.info(f"{proc_name} stdout:")
        for line in stdout_str:
            logger.info(line)

    if log_stderr and logger and completed_proc.stderr:
        stderr_str = (
            completed_proc.stderr.decode("utf8", errors="ignore")
            .strip()
            .split(
                "\n",
            )
        )
        logger.info(f"{proc_name} stderr:")
        for line in stderr_str:
            logger.warning(line)

    # Last, if requested, after logging outputs
    if check_exit_code:
        completed_proc.check_returncode()

    return completed_proc


def get_content_before_last_number(input_string):
    match = re.search(r"(.*)/\d+$", input_string)
    if match:
        return match.group(1)  # Trả về nhóm trước số cuối cùng
    return input_string


def generate_unique_name(name, existing_names):
    i = 1
    new_name = name
    while new_name in existing_names:
        new_name = f"{name}({i})"
        i += 1
    return new_name


def check_storage(capacity=None, directory_to_check=None):
    try:

        if capacity is None:
            capacity = []

        capacity_total = 0
        for c in capacity:
            media_stats = os.statvfs(c)
            total_size = media_stats.f_blocks * media_stats.f_bsize
            # Dung lượng còn lại
            free_size = media_stats.f_bfree * media_stats.f_bsize
            # Dung lượng đã dùng
            used_size = total_size - free_size
            capacity_total += used_size
        directory_to_check_media_stats = os.statvfs(directory_to_check)
        directory_to_check_available = (
            directory_to_check_media_stats.f_frsize
            * directory_to_check_media_stats.f_bavail
        )
        if directory_to_check_available > capacity_total:
            return True
        return False

    except Exception as e:
        logging.error("error check_storage():", e)
        return False


def get_directory_size(directory):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return total_size



def check_digital_signature(pdf_path):
    if not str(pdf_path).lower().endswith('.pdf'):
        return False
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfFileReader(file)
        if '/Sig' in reader.trailer['/Root'].keys():
            return True
        return False

def pdf_has_text_pdftotext(pdf_path: Path) -> bool:
    try:
        with tempfile.NamedTemporaryFile(mode="r+", suffix=".txt") as tmp:
            subprocess.run(
                [
                    "pdftotext",
                    "-q",
                    "-layout",
                    "-enc", "UTF-8",
                    str(pdf_path),
                    tmp.name,
                ],
                check=True
            )
            tmp.seek(0)
            text = tmp.read()
            return bool(text.strip())  # Có text → True
    except Exception as e:

        return False

def get_temp_file_path(file_name_or_path):
    # Lấy tên file cuối cùng
    original_name = Path(file_name_or_path).name

    # An toàn hoá tên file
    safe_name = pathvalidate.sanitize_filename(original_name)

    # Tạo thư mục tạm
    tmp_obj = tempfile.TemporaryDirectory(prefix="edoc-ngx",
                                          dir=settings.SCRATCH_DIR)
    temp_dir = Path(tmp_obj.name)

    # Đảm bảo thư mục tồn tại (dù thường TemporaryDirectory đã tạo)
    temp_dir.mkdir(parents=True, exist_ok=True)

    temp_file_path = temp_dir / safe_name

    return temp_file_path  # Trả lại cả temp_path và object quản lý


def get_unique_name(model, base_name, parent_folder=None):
    unique_name = base_name
    from documents.models import Folder
    # Nếu model là Folder, kiểm tra cả parent_folder
    query = model.objects.filter(name__startswith=unique_name.strip())
    if model == Folder and parent_folder:
        query = query.filter(parent_folder=parent_folder)
    existing_names = query.order_by("name").values_list("name", flat=True)
    # while query.exists():
    #     unique_name = f"{base_name} ({count})"
    #     count += 1
    #     query = model.objects.filter(name=unique_name)
    #     if model == Folder and parent_folder:
    #         query = query.filter(parent_folder=parent_folder)
    #
    # return unique_name
    return generate_unique_name(base_name, existing_names)
