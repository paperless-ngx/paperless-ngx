"""
Table detection and extraction from documents.

This module uses various techniques to detect and extract tables from documents:
1. Image-based detection using deep learning (table-transformer)
2. PDF structure analysis
3. OCR-based table detection
"""

import logging
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


class TableExtractor:
    """
    Extract tables from document images and PDFs.

    Supports multiple extraction methods:
    - Deep learning-based table detection (table-transformer model)
    - PDF structure parsing
    - OCR-based table extraction

    Example:
        >>> extractor = TableExtractor()
        >>> tables = extractor.extract_tables_from_image("invoice.png")
        >>> for table in tables:
        ...     print(table['data'])  # pandas DataFrame
        ...     print(table['bbox'])  # bounding box coordinates
    """

    def __init__(
        self,
        model_name: str = "microsoft/table-transformer-detection",
        confidence_threshold: float = 0.7,
        use_gpu: bool = True,
    ):
        """
        Initialize the table extractor.

        Args:
            model_name: Hugging Face model name for table detection
            confidence_threshold: Minimum confidence score for detection (0-1)
            use_gpu: Whether to use GPU acceleration if available
        """
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.use_gpu = use_gpu
        self._model = None
        self._processor = None

    def _load_model(self):
        """Lazy load the table detection model."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import AutoImageProcessor
            from transformers import AutoModelForObjectDetection

            logger.info(f"Loading table detection model: {self.model_name}")

            self._processor = AutoImageProcessor.from_pretrained(self.model_name)
            self._model = AutoModelForObjectDetection.from_pretrained(self.model_name)

            # Move to GPU if available and requested
            if self.use_gpu and torch.cuda.is_available():
                self._model = self._model.cuda()
                logger.info("Using GPU for table detection")
            else:
                logger.info("Using CPU for table detection")

        except ImportError as e:
            logger.error(f"Failed to load table detection model: {e}")
            logger.error(
                "Please install required packages: pip install transformers torch pillow",
            )
            raise

    def detect_tables(self, image: Image.Image) -> list[dict[str, Any]]:
        """
        Detect tables in an image.

        Args:
            image: PIL Image object

        Returns:
            List of detected tables with bounding boxes and confidence scores
            [
                {
                    'bbox': [x1, y1, x2, y2],  # coordinates
                    'score': 0.95,              # confidence
                    'label': 'table'
                },
                ...
            ]
        """
        self._load_model()

        try:
            import torch

            # Prepare image
            inputs = self._processor(images=image, return_tensors="pt")

            if self.use_gpu and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            # Run detection
            with torch.no_grad():
                outputs = self._model(**inputs)

            # Post-process results
            target_sizes = torch.tensor([image.size[::-1]])
            results = self._processor.post_process_object_detection(
                outputs,
                threshold=self.confidence_threshold,
                target_sizes=target_sizes,
            )[0]

            # Convert to list of dicts
            tables = []
            for score, label, box in zip(
                results["scores"],
                results["labels"],
                results["boxes"],
            ):
                tables.append(
                    {
                        "bbox": box.cpu().tolist(),
                        "score": score.item(),
                        "label": self._model.config.id2label[label.item()],
                    },
                )

            logger.info(f"Detected {len(tables)} tables in image")
            return tables

        except Exception as e:
            logger.error(f"Error detecting tables: {e}")
            return []

    def extract_table_from_region(
        self,
        image: Image.Image,
        bbox: list[float],
        use_ocr: bool = True,
    ) -> dict[str, Any] | None:
        """
        Extract table data from a specific region of an image.

        Args:
            image: PIL Image object
            bbox: Bounding box [x1, y1, x2, y2]
            use_ocr: Whether to use OCR for text extraction

        Returns:
            Extracted table data as dictionary with 'data' (pandas DataFrame)
            and 'raw_text' keys, or None if extraction failed
        """
        try:
            # Crop to table region
            x1, y1, x2, y2 = [int(coord) for coord in bbox]
            table_image = image.crop((x1, y1, x2, y2))

            if use_ocr:
                # Use OCR to extract text and structure
                import pytesseract

                # Get detailed OCR data
                ocr_data = pytesseract.image_to_data(
                    table_image,
                    output_type=pytesseract.Output.DICT,
                )

                # Reconstruct table structure from OCR data
                table_data = self._reconstruct_table_from_ocr(ocr_data)

                # Also get raw text
                raw_text = pytesseract.image_to_string(table_image)

                return {
                    "data": table_data,
                    "raw_text": raw_text,
                    "bbox": bbox,
                    "image_size": table_image.size,
                }
            else:
                # Fallback to basic OCR without structure
                import pytesseract

                raw_text = pytesseract.image_to_string(table_image)
                return {
                    "data": None,
                    "raw_text": raw_text,
                    "bbox": bbox,
                    "image_size": table_image.size,
                }

        except ImportError:
            logger.error(
                "pytesseract not installed. Install with: pip install pytesseract",
            )
            return None
        except Exception as e:
            logger.error(f"Error extracting table from region: {e}")
            return None

    def _reconstruct_table_from_ocr(self, ocr_data: dict) -> Any | None:
        """
        Reconstruct table structure from OCR output.

        Args:
            ocr_data: OCR data from pytesseract

        Returns:
            pandas DataFrame or None if reconstruction failed
        """
        try:
            import pandas as pd

            # Group text by vertical position (rows)
            rows = {}
            for i, text in enumerate(ocr_data["text"]):
                if text.strip():
                    top = ocr_data["top"][i]
                    left = ocr_data["left"][i]

                    # Group by approximate row (within 20 pixels)
                    row_key = round(top / 20) * 20
                    if row_key not in rows:
                        rows[row_key] = []
                    rows[row_key].append((left, text))

            # Sort rows and create DataFrame
            table_rows = []
            for row_y in sorted(rows.keys()):
                # Sort cells by horizontal position
                cells = [text for _, text in sorted(rows[row_y])]
                table_rows.append(cells)

            if table_rows:
                # Pad rows to same length
                max_cols = max(len(row) for row in table_rows)
                table_rows = [row + [""] * (max_cols - len(row)) for row in table_rows]

                # Create DataFrame
                df = pd.DataFrame(table_rows)

                # Try to use first row as header if it looks like one
                if len(df) > 1:
                    first_row_text = " ".join(str(x) for x in df.iloc[0])
                    if not any(char.isdigit() for char in first_row_text):
                        df.columns = df.iloc[0]
                        df = df[1:].reset_index(drop=True)

                return df

            return None

        except ImportError:
            logger.error("pandas not installed. Install with: pip install pandas")
            return None
        except Exception as e:
            logger.error(f"Error reconstructing table: {e}")
            return None

    def extract_tables_from_image(
        self,
        image_path: str,
        output_format: str = "dataframe",
    ) -> list[dict[str, Any]]:
        """
        Extract all tables from an image file.

        Args:
            image_path: Path to image file
            output_format: 'dataframe' or 'csv' or 'json'

        Returns:
            List of extracted tables with data and metadata
        """
        try:
            # Load image
            image = Image.open(image_path).convert("RGB")

            # Detect tables
            detections = self.detect_tables(image)

            # Extract data from each table
            tables = []
            for i, detection in enumerate(detections):
                logger.info(f"Extracting table {i + 1}/{len(detections)}")

                table_data = self.extract_table_from_region(
                    image,
                    detection["bbox"],
                )

                if table_data:
                    table_data["detection_score"] = detection["score"]
                    table_data["table_index"] = i

                    # Convert to requested format
                    if output_format == "csv" and table_data["data"] is not None:
                        table_data["csv"] = table_data["data"].to_csv(index=False)
                    elif output_format == "json" and table_data["data"] is not None:
                        table_data["json"] = table_data["data"].to_json(
                            orient="records",
                        )

                    tables.append(table_data)

            logger.info(
                f"Successfully extracted {len(tables)} tables from {image_path}",
            )
            return tables

        except Exception as e:
            logger.error(f"Error extracting tables from image {image_path}: {e}")
            return []

    def extract_tables_from_pdf(
        self,
        pdf_path: str,
        page_numbers: list[int] | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        """
        Extract tables from a PDF document.

        Args:
            pdf_path: Path to PDF file
            page_numbers: List of page numbers to process (1-indexed), or None for all pages

        Returns:
            Dictionary mapping page numbers to lists of extracted tables
        """
        try:
            from pdf2image import convert_from_path

            logger.info(f"Converting PDF to images: {pdf_path}")

            # Convert PDF pages to images
            if page_numbers:
                images = convert_from_path(
                    pdf_path,
                    first_page=min(page_numbers),
                    last_page=max(page_numbers),
                )
            else:
                images = convert_from_path(pdf_path)

            # Extract tables from each page
            results = {}
            for i, image in enumerate(images):
                page_num = page_numbers[i] if page_numbers else i + 1
                logger.info(f"Processing page {page_num}")

                # Detect and extract tables
                detections = self.detect_tables(image)
                tables = []

                for detection in detections:
                    table_data = self.extract_table_from_region(
                        image,
                        detection["bbox"],
                    )
                    if table_data:
                        table_data["detection_score"] = detection["score"]
                        table_data["page"] = page_num
                        tables.append(table_data)

                if tables:
                    results[page_num] = tables
                    logger.info(f"Found {len(tables)} tables on page {page_num}")

            return results

        except ImportError:
            logger.error("pdf2image not installed. Install with: pip install pdf2image")
            return {}
        except Exception as e:
            logger.error(f"Error extracting tables from PDF: {e}")
            return {}

    def save_tables_to_excel(
        self,
        tables: list[dict[str, Any]],
        output_path: str,
    ) -> bool:
        """
        Save extracted tables to an Excel file.

        Args:
            tables: List of table dictionaries with 'data' key containing DataFrame
            output_path: Path to output Excel file

        Returns:
            True if successful, False otherwise
        """
        try:
            import pandas as pd

            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                for i, table in enumerate(tables):
                    if table.get("data") is not None:
                        sheet_name = f"Table_{i + 1}"
                        if "page" in table:
                            sheet_name = f"Page_{table['page']}_Table_{i + 1}"

                        table["data"].to_excel(
                            writer,
                            sheet_name=sheet_name,
                            index=False,
                        )

            logger.info(f"Saved {len(tables)} tables to {output_path}")
            return True

        except ImportError:
            logger.error("openpyxl not installed. Install with: pip install openpyxl")
            return False
        except Exception as e:
            logger.error(f"Error saving tables to Excel: {e}")
            return False
