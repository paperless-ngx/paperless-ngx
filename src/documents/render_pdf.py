import io
import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter, PageObject
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from io import BytesIO
import math

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

def draw_invisible_text(input_path, output_path, data):
    if is_image_file(input_path):
        doc = create_pdf_from_image(input_path)
    elif is_pdf_file(input_path):
        doc = fitz.open(input_path)
    else:
        raise ValueError(
            "Unsupported file format. Please provide a PDF or image.")
    for page_num in range(len(doc)):
        page = doc[page_num]

        width = page.rect.width
        height = page.rect.height

        width_api_img = data["pages"][page_num]["dimensions"][1]
        height_api_img = data["pages"][page_num]["dimensions"][0]

        rolate_width = width_api_img / width
        rolate_height = height_api_img / height

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
                    page.insert_text(
                        fitz.Point(x1, y2),
                        value,
                        fontsize=font_size,
                        color=(1, 1, 1),  # Màu trắng
                        render_mode=3,     # render_mode=3 = invisible text
                        fontname='helv'
                    )

    doc.save(output_path)

