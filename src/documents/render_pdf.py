import io
import logging
import shutil
from pathlib import Path

from PIL import Image
from PyPDF2 import PdfReader as pypdf2_pdfreader
from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from documents.utils import get_temp_file_path

logger = logging.getLogger("edoc.render_pdf")
logging.basicConfig(level=logging.INFO)

def create_overlay(width, height, text_data, font_path):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(width, height))
    pdfmetrics.registerFont(TTFont("Arial", font_path))
    can.setFont("Arial", 12)

    for word in text_data:
        value = word["value"]
        x = word["x"]
        y = word["y"]
        font_size = word["font_size"]
        can.setFont("Arial", font_size)
        can.drawString(x, y, value)

    can.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]


def draw_text_on_pdf(input_path, output_path, data, font_path):
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page_num, page in enumerate(reader.pages):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        # Chuẩn bị dữ liệu text
        width_api_img = data["pages"][page_num]["dimensions"][1]
        height_api_img = data["pages"][page_num]["dimensions"][0]
        rolate_width = width_api_img / width
        rolate_height = height_api_img / height

        text_data = []
        for block in data["pages"][page_num]["blocks"]:
            for line in block.get("lines", []):
                for word in line.get("words", []):
                    x1 = word["bbox"][0][0] / float(rolate_width)
                    y1 = word["bbox"][0][1] / float(rolate_height)
                    x2 = word["bbox"][1][0] / float(rolate_width)
                    y2 = word["bbox"][1][1] / float(rolate_height)

                    font_size = max(1, math.floor((y2 - y1) * 72 / 96))
                    value = word["value"]
                    x_center = x2 - (x2 - x1) / 2
                    y_center = y2 - (y2 - y1) / 2

                    text_data.append({
                        "value": value,
                        "x": int(x_center),
                        "y": int(float(height) - y_center - font_size / 2),
                        "font_size": font_size,
                    })

        # Tạo overlay và merge
        overlay = create_overlay(width, height, text_data, font_path)
        page.merge_page(overlay)
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

import fitz  # PyMuPDF
import math


VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".bmp", ".webp"}
VALID_PDF_EXTENSIONS = {".pdf"}

def is_image_file(path: Path):
    return path.suffix.lower() in VALID_IMAGE_EXTENSIONS

def is_pdf_file(path: Path):
    return path.suffix.lower() == ".pdf"

def create_pdf_from_image(image_path):
    img_doc = fitz.open(image_path)
    rect = img_doc[0].rect
    img_pdf = fitz.open("pdf", img_doc.convert_to_pdf())

    doc = fitz.open()
    page = doc.new_page(width=rect.width, height=rect.height)
    page.show_pdf_page(rect, img_pdf, 0)
    return doc



def rotate_point(x, y, angle):
    # Chuyển đổi góc sang radian
    radians = math.radians(angle)
    # Tính toán tọa độ mới sau khi xoay
    x_new = x * math.cos(radians) + y * math.sin(radians)
    y_new = -x * math.sin(radians) + y * math.cos(radians)
    return round(x_new, 2), round(y_new, 2)


def draw_invisible_text(input_path, output_path, data, quality = 85, font_path=''):
    if is_image_file(input_path):
        doc = create_pdf_from_image(input_path)
    elif is_pdf_file(input_path):
        doc = fitz.open(input_path)
    else:
        raise ValueError(
            "Unsupported file format. Please provide a PDF or image.")

    for page_num in range(len(doc)):
        page = doc[page_num]
        if font_path:
            page.insert_font(fontfile=font_path, fontname="font_name",
                    set_simple=False)

        width = page.rect.width
        height = page.rect.height

        width_api_img = data["pages"][page_num]["dimensions"][1]
        height_api_img = data["pages"][page_num]["dimensions"][0]
        logger.info(f'api: w{width_api_img},h {height_api_img}-------pdf reader: w: {width}, h:{height}')

        rolate_width = width_api_img / width
        rolate_height = height_api_img / height
        logging.info(
            f"rolate_width: {rolate_width}, rolate_height: {rolate_height}")
        page_rotation = page.rotation
        # if page.rotation != 0:
        #     page.set_rotation(0)



        for block in data["pages"][page_num]["blocks"]:
            for line in block.get("lines", []):
                for word in line.get("words", []):
                    x1 = word["bbox"][0][0] / float(rolate_width)
                    y1 = word["bbox"][0][1] / float(rolate_height)
                    x2 = word["bbox"][1][0] / float(rolate_width)
                    y2 = word["bbox"][1][1] / float(rolate_height)

                    font_size = max(1, math.floor((y2 - y1) * 72 / 96))
                    value = word["value"]

                    x_center = x2 - (x2 - x1)
                    y_center = y2 - (y2 - y1)

                    # Tọa độ trong PyMuPDF bắt đầu từ trên cùng (y tăng xuống dưới)
                    insert_x = x_center
                    insert_y = y_center

                    # Add invisible text
                    point = fitz.Point(x1, y2)
                    if page.rotation != 0:
                        point = fitz.Point(height-y2, x1)
                    page.insert_text(
                        point,
                        value,
                        fontsize=font_size,
                        color=(1, 1, 1),  # Màu trắng
                        render_mode=3,     # render_mode=3 = invisible text
                        fontname = 'font_name' if font_path else 'Helv',
                        rotate = page_rotation


                    )
        # if page_rotation > 0:
        #     logger.info(f"Page rotation: {page.rotation} -> resetting to 0")
        #     page.set_rotation(page_rotation)

    # file_temp=get_temp_file_path(output_path)
    # if not file_temp.exists():
    #     file_temp.parent.mkdir(parents=True, exist_ok=True)


    # logger.info("file_temp---------------", file_temp)
    # doc.save(file_temp)
    doc.save(output_path)
    logger.info('đã lưu xong')
    # smart_compress(file_temp, output_path, quality=quality)


def render_pdf_ocr(input_path, output_path,
                       data_ocr, quality_compress = 85, font_path=''):
    font_name = 'Arial'
    data = data_ocr or {}
    if is_image_file(input_path):
        img = Image.open(input_path)
        width, height = img.size
        c = canvas.Canvas(str(output_path), pagesize=(width, height))
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        # c.drawImage(input_path, 0, 0, width=width, height=height)
        for page in data.get("pages", {}):
            for block in page["blocks"]:
                for line in block.get("lines", []):
                    y1 = line.get("bbox")[0][1]
                    y2 = line.get("bbox")[1][1]
                    font_size = math.floor((y2 - y1) * 72 / 96)
                    y_center_coordinates = y2 - (y2 - y1) / 2
                    for word in line.get("words", []):
                        x1 = word["bbox"][0][0]
                        # y1 = word["bbox"][0][1]
                        x2 = word["bbox"][1][0]
                        # y2 = word["bbox"][1][1]
                        value = word["value"]
                        # font_size = math.ceil(float(y2-y1) * 72 / 96)
                        # font_size = (y2-y1) * 72 / 96
                        x_center_coordinates = x2 - (x2 - x1) / 2
                        # y_center_coordinates =y2 - (y2-y1)/2
                        w = c.stringWidth(value, font_name, font_size)
                        c.setFont('Arial', font_size)
                        c.drawString(x_center_coordinates - w / 2,
                                     height - y_center_coordinates - (
                                         font_size / 2),
                                     value)
        c.drawImage(input_path, 0, 0, width=width, height=height)
        c.save()
    elif is_pdf_file(input_path):
        shutil.copy(str(input_path), str(output_path))
        if len(data) < 1:
            return

        input_pdf = pypdf2_pdfreader(input_path)
        file_temp = get_temp_file_path(output_path)
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
        can = canvas.Canvas(str(output_path), pagesize=letter)

        pdfmetrics.registerFont(TTFont('Arial', font_path))
        font_name = "Arial"

        for page_num, page in enumerate(input_pdf.pages):
            image = convert_from_path(input_path,
                                      first_page=page_num + 1,
                                      last_page=page_num + 2, use_cropbox=True,
                                      strict=False)[0]

            page_height = page.mediabox.getHeight()
            page_width = page.mediabox.getWidth()

            width_api_img = data["pages"][page_num]["dimensions"][1]
            height_api_img = data["pages"][page_num]["dimensions"][0]

            # set size new page
            if width_api_img < height_api_img and page_height < page_width:
                page_height, page_width = page_width, page_height

            can.setPageSize((page_width, page_height))

            byte_image = io.BytesIO()
            image.save(byte_image, format='JPEG',
                       quality=30, optimize=True)
            byte_image.seek(0)

            rolate_height = height_api_img / page_height
            rolate_width = width_api_img / page_width

            for block in data["pages"][page_num]["blocks"]:
                for line in block.get("lines", []):
                    y1_line = (
                        line.get("bbox")[0][1] / float(rolate_height))
                    y2_line = (
                        line.get("bbox")[1][1] / float(rolate_height))

                    y_center_coordinates = y2_line - (
                        y2_line - y1_line) / 2
                    font_size = max(1,
                                    math.floor((int(y2_line) - int(
                                        y1_line)) * 72 / 96))
                    can.setFont('Arial', font_size - 2)
                    for word in line.get("words", []):
                        x1 = word["bbox"][0][0] / float(rolate_width)
                        y1 = word["bbox"][0][1] / float(rolate_height)
                        x2 = word["bbox"][1][0] / float(rolate_width)
                        y2 = word["bbox"][1][1] / float(rolate_height)

                        value = word["value"]
                        x_center_coordinates = x2 - (x2 - x1) / 2

                        w = can.stringWidth(value, font_name, font_size - 2)

                        can.drawString(int(x_center_coordinates - w / 2),
                                       int(float(
                                           page_height) - y_center_coordinates - (
                                               font_size / 2)) + 2,
                                       value)
            can.drawImage(ImageReader(byte_image),
                          0, 0,
                          width=float(page_width),
                          height=float(page_height))
            can.showPage()
        # can.save()
        # can._filename=f'{Path(__file__).resolve().parent.parent.parent}/media/archive-fallback.pdf'
        can.save()

        # logger.info("file_temp---------------", file_temp)
        # doc.save(file_temp)
        # doc.save(output_path)
        logger.info('đã lưu xong')

        # doc = fitz.open(input_path)
    else:
        raise ValueError(
            "Unsupported file format. Please provide a PDF or image.")


