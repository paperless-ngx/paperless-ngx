"""
Form field detection and recognition.

This module provides capabilities to:
1. Detect form fields (checkboxes, text fields, labels)
2. Extract field values
3. Map fields to structured data
"""

import logging
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class FormFieldDetector:
    """
    Detect and extract form fields from document images.
    
    Supports:
    - Text field detection
    - Checkbox detection and state recognition
    - Label association
    - Value extraction
    
    Example:
        >>> detector = FormFieldDetector()
        >>> fields = detector.detect_form_fields("form.jpg")
        >>> for field in fields:
        ...     print(f"{field['label']}: {field['value']}")
        
        >>> # Extract specific field types
        >>> checkboxes = detector.detect_checkboxes("form.jpg")
        >>> for cb in checkboxes:
        ...     print(f"{cb['label']}: {'✓' if cb['checked'] else '☐'}")
    """

    def __init__(self, use_gpu: bool = True):
        """
        Initialize the form field detector.
        
        Args:
            use_gpu: Whether to use GPU acceleration if available
        """
        self.use_gpu = use_gpu
        self._handwriting_recognizer = None

    def _get_handwriting_recognizer(self):
        """Lazy load handwriting recognizer for field value extraction."""
        if self._handwriting_recognizer is None:
            from .handwriting import HandwritingRecognizer
            self._handwriting_recognizer = HandwritingRecognizer(use_gpu=self.use_gpu)
        return self._handwriting_recognizer

    def detect_checkboxes(
        self,
        image: Image.Image,
        min_size: int = 10,
        max_size: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Detect checkboxes in a form image.
        
        Args:
            image: PIL Image object
            min_size: Minimum checkbox size in pixels
            max_size: Maximum checkbox size in pixels
            
        Returns:
            List of detected checkboxes with state
            [
                {
                    'bbox': [x1, y1, x2, y2],
                    'checked': True/False,
                    'confidence': 0.95
                },
                ...
            ]
        """
        try:
            import cv2

            # Convert to OpenCV format
            img_array = np.array(image)
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            # Detect edges
            edges = cv2.Canny(gray, 50, 150)

            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            checkboxes = []
            for contour in contours:
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)

                # Check if it looks like a checkbox (square-ish, right size)
                aspect_ratio = w / h if h > 0 else 0
                if (min_size <= w <= max_size and
                    min_size <= h <= max_size and
                    0.7 <= aspect_ratio <= 1.3):

                    # Extract checkbox region
                    checkbox_region = gray[y:y+h, x:x+w]

                    # Determine if checked (look for marks inside)
                    checked, confidence = self._is_checkbox_checked(checkbox_region)

                    checkboxes.append({
                        "bbox": [x, y, x+w, y+h],
                        "checked": checked,
                        "confidence": confidence,
                    })

            logger.info(f"Detected {len(checkboxes)} checkboxes")
            return checkboxes

        except ImportError:
            logger.error("opencv-python not installed. Install with: pip install opencv-python")
            return []
        except Exception as e:
            logger.error(f"Error detecting checkboxes: {e}")
            return []

    def _is_checkbox_checked(self, checkbox_image: np.ndarray) -> tuple[bool, float]:
        """
        Determine if a checkbox is checked.
        
        Args:
            checkbox_image: Grayscale image of checkbox
            
        Returns:
            Tuple of (is_checked, confidence)
        """
        try:
            import cv2

            # Binarize
            _, binary = cv2.threshold(checkbox_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # Count dark pixels in the center region (where mark would be)
            h, w = binary.shape
            center_region = binary[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]

            if center_region.size == 0:
                return False, 0.0

            dark_pixel_ratio = np.sum(center_region > 0) / center_region.size

            # If more than 15% of center is dark, consider it checked
            checked = dark_pixel_ratio > 0.15
            confidence = min(dark_pixel_ratio * 2, 1.0)  # Scale confidence

            return checked, confidence

        except Exception as e:
            logger.warning(f"Error checking checkbox state: {e}")
            return False, 0.0

    def detect_text_fields(
        self,
        image: Image.Image,
        min_width: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Detect text input fields in a form.
        
        Args:
            image: PIL Image object
            min_width: Minimum field width in pixels
            
        Returns:
            List of detected text fields
            [
                {
                    'bbox': [x1, y1, x2, y2],
                    'type': 'line' or 'box'
                },
                ...
            ]
        """
        try:
            import cv2

            # Convert to OpenCV format
            img_array = np.array(image)
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            # Detect horizontal lines (underlines for text fields)
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_width, 1))
            detect_horizontal = cv2.morphologyEx(
                cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1],
                cv2.MORPH_OPEN,
                horizontal_kernel,
                iterations=2,
            )

            # Find contours of horizontal lines
            contours, _ = cv2.findContours(
                detect_horizontal,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )

            text_fields = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)

                # Check if it's a horizontal line (field underline)
                if w >= min_width and h < 10:
                    # Expand upward to include text area
                    text_bbox = [x, max(0, y-30), x+w, y+h]
                    text_fields.append({
                        "bbox": text_bbox,
                        "type": "line",
                    })

            # Detect rectangular boxes (bordered text fields)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)

                # Check if it's a rectangular box
                aspect_ratio = w / h if h > 0 else 0
                if w >= min_width and 20 <= h <= 100 and aspect_ratio > 2:
                    text_fields.append({
                        "bbox": [x, y, x+w, y+h],
                        "type": "box",
                    })

            logger.info(f"Detected {len(text_fields)} text fields")
            return text_fields

        except ImportError:
            logger.error("opencv-python not installed")
            return []
        except Exception as e:
            logger.error(f"Error detecting text fields: {e}")
            return []

    def detect_labels(
        self,
        image: Image.Image,
        field_bboxes: list[list[int]],
    ) -> list[dict[str, Any]]:
        """
        Detect labels near form fields.
        
        Args:
            image: PIL Image object
            field_bboxes: List of field bounding boxes [[x1,y1,x2,y2], ...]
            
        Returns:
            List of detected labels with associated field indices
        """
        try:
            import pytesseract

            # Get all text with bounding boxes
            ocr_data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
            )

            # Group text into potential labels
            labels = []
            for i, text in enumerate(ocr_data["text"]):
                if text.strip() and len(text.strip()) > 2:
                    x = ocr_data["left"][i]
                    y = ocr_data["top"][i]
                    w = ocr_data["width"][i]
                    h = ocr_data["height"][i]

                    label_bbox = [x, y, x+w, y+h]

                    # Find closest field
                    closest_field_idx = self._find_closest_field(label_bbox, field_bboxes)

                    labels.append({
                        "text": text.strip(),
                        "bbox": label_bbox,
                        "field_index": closest_field_idx,
                    })

            return labels

        except ImportError:
            logger.error("pytesseract not installed")
            return []
        except Exception as e:
            logger.error(f"Error detecting labels: {e}")
            return []

    def _find_closest_field(
        self,
        label_bbox: list[int],
        field_bboxes: list[list[int]],
    ) -> int | None:
        """
        Find the closest field to a label.
        
        Args:
            label_bbox: Label bounding box [x1, y1, x2, y2]
            field_bboxes: List of field bounding boxes
            
        Returns:
            Index of closest field, or None if no fields
        """
        if not field_bboxes:
            return None

        # Calculate center of label
        label_center_x = (label_bbox[0] + label_bbox[2]) / 2
        label_center_y = (label_bbox[1] + label_bbox[3]) / 2

        min_distance = float("inf")
        closest_idx = 0

        for i, field_bbox in enumerate(field_bboxes):
            # Calculate center of field
            field_center_x = (field_bbox[0] + field_bbox[2]) / 2
            field_center_y = (field_bbox[1] + field_bbox[3]) / 2

            # Euclidean distance
            distance = np.sqrt(
                (label_center_x - field_center_x)**2 +
                (label_center_y - field_center_y)**2,
            )

            if distance < min_distance:
                min_distance = distance
                closest_idx = i

        return closest_idx

    def detect_form_fields(
        self,
        image_path: str,
        extract_values: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Detect all form fields and extract their values.
        
        Args:
            image_path: Path to form image
            extract_values: Whether to extract field values using OCR
            
        Returns:
            List of detected fields with labels and values
            [
                {
                    'type': 'text' or 'checkbox',
                    'label': 'Field Label',
                    'value': 'field value' or True/False,
                    'bbox': [x1, y1, x2, y2],
                    'confidence': 0.95
                },
                ...
            ]
        """
        try:
            # Load image
            image = Image.open(image_path).convert("RGB")

            # Detect different field types
            text_fields = self.detect_text_fields(image)
            checkboxes = self.detect_checkboxes(image)

            # Combine all field bboxes for label detection
            all_field_bboxes = [f["bbox"] for f in text_fields] + [cb["bbox"] for cb in checkboxes]

            # Detect labels
            labels = self.detect_labels(image, all_field_bboxes)

            # Build results
            results = []

            # Add text fields
            for i, field in enumerate(text_fields):
                # Find associated label
                label_text = self._find_label_for_field(i, labels, len(text_fields))

                result = {
                    "type": "text",
                    "label": label_text,
                    "bbox": field["bbox"],
                }

                # Extract value if requested
                if extract_values:
                    x1, y1, x2, y2 = field["bbox"]
                    field_image = image.crop((x1, y1, x2, y2))

                    recognizer = self._get_handwriting_recognizer()
                    value = recognizer.recognize_from_image(field_image, preprocess=True)
                    result["value"] = value.strip()
                    result["confidence"] = recognizer._estimate_confidence(value)

                results.append(result)

            # Add checkboxes
            for i, checkbox in enumerate(checkboxes):
                field_idx = len(text_fields) + i
                label_text = self._find_label_for_field(field_idx, labels, len(all_field_bboxes))

                results.append({
                    "type": "checkbox",
                    "label": label_text,
                    "value": checkbox["checked"],
                    "bbox": checkbox["bbox"],
                    "confidence": checkbox["confidence"],
                })

            logger.info(f"Detected {len(results)} form fields from {image_path}")
            return results

        except Exception as e:
            logger.error(f"Error detecting form fields: {e}")
            return []

    def _find_label_for_field(
        self,
        field_idx: int,
        labels: list[dict[str, Any]],
        total_fields: int,
    ) -> str:
        """
        Find the label text for a specific field.
        
        Args:
            field_idx: Index of the field
            labels: List of detected labels
            total_fields: Total number of fields
            
        Returns:
            Label text or empty string if not found
        """
        matching_labels = [
            label for label in labels
            if label["field_index"] == field_idx
        ]

        if matching_labels:
            # Combine multiple label parts if found
            return " ".join(label["text"] for label in matching_labels)

        return f"Field_{field_idx + 1}"

    def extract_form_data(
        self,
        image_path: str,
        output_format: str = "dict",
    ) -> Any:
        """
        Extract all form data as structured output.
        
        Args:
            image_path: Path to form image
            output_format: Output format ('dict', 'json', or 'dataframe')
            
        Returns:
            Structured form data in requested format
        """
        # Detect and extract fields
        fields = self.detect_form_fields(image_path, extract_values=True)

        if output_format == "dict":
            # Return as dictionary
            return {field["label"]: field["value"] for field in fields}

        elif output_format == "json":
            import json
            data = {field["label"]: field["value"] for field in fields}
            return json.dumps(data, indent=2)

        elif output_format == "dataframe":
            import pandas as pd
            return pd.DataFrame(fields)

        else:
            raise ValueError(f"Invalid output format: {output_format}")
