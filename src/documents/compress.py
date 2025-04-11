import subprocess
from pathlib import Path
from PIL import Image
import logging

logger = logging.getLogger("edoc.compress")
logging.basicConfig(level=logging.INFO)


def map_quality_to_setting(quality):
    if quality < 30:
        return "/screen"
    elif quality < 50:
        return "/ebook"
    elif quality < 80:
        return "/printer"
    else:
        return "/prepress"


def compress_pdf(input_path, output_path, quality=80):
    setting = map_quality_to_setting(quality)
    cmd = [
        "gs", "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={setting}",
        "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={output_path}",
        str(input_path)
    ]
    try:
        subprocess.run(cmd, check=True)
        logger.info(f"✔️ Nén PDF xong: {output_path} (quality={quality}, setting={setting})")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Lỗi nén PDF: {e}")


def compress_jpg(input_path, output_path, quality=80):
    try:
        img = Image.open(input_path)
        img.save(output_path, "JPEG", optimize=True, quality=quality)
        logger.info(f"✔️ Nén JPG xong: {output_path} (quality={quality})")
    except Exception as e:
        logger.error(f"❌ Lỗi nén JPG: {e}")


def compress_png(input_path, output_path, quality=80):
    try:
        img = Image.open(input_path)
        img = img.convert("P", palette=Image.ADAPTIVE)
        img.save(output_path, format="PNG", optimize=True)
        logger.info(f"✔️ Nén PNG xong: {output_path}")
    except Exception as e:
        logger.error(f"❌ Lỗi nén PNG: {e}")


def compress_webp(input_path, output_path, quality=80):
    try:
        img = Image.open(input_path)
        img.save(output_path, "WEBP", quality=quality, method=6)
        logger.info(f"✔️ Nén WEBP xong: {output_path} (quality={quality})")
    except Exception as e:
        logger.error(f"❌ Lỗi nén WEBP: {e}")


def compress_tiff(input_path, output_path):
    try:
        img = Image.open(input_path)
        img.save(output_path, "TIFF", compression="tiff_deflate")
        logger.info(f"✔️ Nén TIFF xong: {output_path}")
    except Exception as e:
        logger.error(f"❌ Lỗi nén TIFF: {e}")


def compress_gif(input_path, output_path):
    try:
        img = Image.open(input_path)
        img = img.convert("P", palette=Image.ADAPTIVE)
        img.save(output_path, format="GIF", optimize=True)
        logger.info(f"✔️ Nén GIF xong: {output_path}")
    except Exception as e:
        logger.error(f"❌ Lỗi nén GIF: {e}")


def compress_bmp(input_path, output_path):
    try:
        img = Image.open(input_path)
        img.save(output_path, format="PNG", optimize=True)
        logger.info(f"✔️ Nén BMP xong (chuyển sang PNG): {output_path}")
    except Exception as e:
        logger.error(f"❌ Lỗi nén BMP: {e}")

def smart_compress(input_path: str, output_path: str, quality: int = 85) -> bool:
    ext = Path(input_path).suffix.lower()
    logger.info(f"🔍 Đang xử lý nén: {input_path} → {output_path} (ext={ext}, quality={quality})")

    try:
        if ext == ".pdf":
            compress_pdf(input_path, output_path, quality)
        elif ext in [".jpg", ".jpeg"]:
            compress_jpg(input_path, output_path, quality)
        elif ext == ".png":
            compress_png(input_path, output_path, quality)
        elif ext == ".webp":
            compress_webp(input_path, output_path, quality)
        elif ext in [".tif", ".tiff"]:
            compress_tiff(input_path, output_path)
        elif ext == ".gif":
            compress_gif(input_path, output_path)
        elif ext == ".bmp":
            compress_bmp(input_path, output_path)
        else:
            logger.warning(f"⚠️ Định dạng chưa hỗ trợ: {ext}")
            return False

        return True

    except Exception as e:
        logger.error(f"❌ Lỗi khi nén file: {e}")
        return False
