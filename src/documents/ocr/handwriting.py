"""
Handwriting recognition for documents.

This module provides handwriting OCR capabilities using:
1. TrOCR (Transformer-based OCR) for printed and handwritten text
2. Custom models fine-tuned for specific handwriting styles
3. Confidence scoring for recognition quality
"""

import logging
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class HandwritingRecognizer:
    """
    Recognize handwritten text from document images.
    
    Uses transformer-based models (TrOCR) for accurate handwriting recognition.
    Supports both printed and handwritten text detection.
    
    Example:
        >>> recognizer = HandwritingRecognizer()
        >>> text = recognizer.recognize_from_image("handwritten_note.jpg")
        >>> print(text)
        "This is handwritten text..."
        
        >>> # With line detection
        >>> lines = recognizer.recognize_lines("form.jpg")
        >>> for line in lines:
        ...     print(f"{line['text']} (confidence: {line['confidence']:.2f})")
    """

    def __init__(
        self,
        model_name: str = "microsoft/trocr-base-handwritten",
        use_gpu: bool = True,
        confidence_threshold: float = 0.5,
    ):
        """
        Initialize the handwriting recognizer.
        
        Args:
            model_name: Hugging Face model name
                Options:
                - "microsoft/trocr-base-handwritten" (default, good for English)
                - "microsoft/trocr-large-handwritten" (more accurate, slower)
                - "microsoft/trocr-base-printed" (for printed text)
            use_gpu: Whether to use GPU acceleration if available
            confidence_threshold: Minimum confidence for accepting recognition
        """
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._processor = None

    def _load_model(self):
        """Lazy load the handwriting recognition model."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import TrOCRProcessor
            from transformers import VisionEncoderDecoderModel

            logger.info(f"Loading handwriting recognition model: {self.model_name}")

            self._processor = TrOCRProcessor.from_pretrained(self.model_name)
            self._model = VisionEncoderDecoderModel.from_pretrained(self.model_name)

            # Move to GPU if available and requested
            if self.use_gpu and torch.cuda.is_available():
                self._model = self._model.cuda()
                logger.info("Using GPU for handwriting recognition")
            else:
                logger.info("Using CPU for handwriting recognition")

            self._model.eval()  # Set to evaluation mode

        except ImportError as e:
            logger.error(f"Failed to load handwriting model: {e}")
            logger.error("Please install: pip install transformers torch pillow")
            raise

    def recognize_from_image(
        self,
        image: Image.Image,
        preprocess: bool = True,
    ) -> str:
        """
        Recognize text from a single image.
        
        Args:
            image: PIL Image object containing handwritten text
            preprocess: Whether to preprocess image (contrast, binarization)
            
        Returns:
            Recognized text string
        """
        self._load_model()

        try:
            import torch

            # Preprocess image if requested
            if preprocess:
                image = self._preprocess_image(image)

            # Prepare image for model
            pixel_values = self._processor(images=image, return_tensors="pt").pixel_values

            if self.use_gpu and torch.cuda.is_available():
                pixel_values = pixel_values.cuda()

            # Generate text
            with torch.no_grad():
                generated_ids = self._model.generate(pixel_values)

            # Decode to text
            text = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

            logger.debug(f"Recognized text: {text[:100]}...")
            return text

        except Exception as e:
            logger.error(f"Error recognizing handwriting: {e}")
            return ""

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better recognition.
        
        Args:
            image: Input PIL Image
            
        Returns:
            Preprocessed PIL Image
        """
        try:
            from PIL import ImageEnhance
            from PIL import ImageFilter

            # Convert to grayscale
            if image.mode != "L":
                image = image.convert("L")

            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)

            # Denoise
            image = image.filter(ImageFilter.MedianFilter(size=3))

            # Convert back to RGB (required by model)
            image = image.convert("RGB")

            return image

        except Exception as e:
            logger.warning(f"Error preprocessing image: {e}")
            return image

    def detect_text_lines(self, image: Image.Image) -> list[dict[str, Any]]:
        """
        Detect individual text lines in an image.
        
        Args:
            image: PIL Image object
            
        Returns:
            List of detected lines with bounding boxes
            [
                {
                    'bbox': [x1, y1, x2, y2],
                    'image': PIL.Image
                },
                ...
            ]
        """
        try:
            import cv2
            import numpy as np

            # Convert PIL to OpenCV format
            img_array = np.array(image)
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            # Binarize
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # Find contours
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Get bounding boxes for each contour
            lines = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)

                # Filter out very small regions
                if w > 20 and h > 10:
                    # Crop line from original image
                    line_img = image.crop((x, y, x+w, y+h))
                    lines.append({
                        "bbox": [x, y, x+w, y+h],
                        "image": line_img,
                    })

            # Sort lines top to bottom
            lines.sort(key=lambda l: l["bbox"][1])

            logger.info(f"Detected {len(lines)} text lines")
            return lines

        except ImportError:
            logger.error("opencv-python not installed. Install with: pip install opencv-python")
            return []
        except Exception as e:
            logger.error(f"Error detecting text lines: {e}")
            return []

    def recognize_lines(
        self,
        image_path: str,
        return_confidence: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Recognize text from each line in an image.
        
        Args:
            image_path: Path to image file
            return_confidence: Whether to include confidence scores
            
        Returns:
            List of recognized lines with text and metadata
            [
                {
                    'text': 'recognized text',
                    'bbox': [x1, y1, x2, y2],
                    'confidence': 0.95
                },
                ...
            ]
        """
        try:
            # Load image
            image = Image.open(image_path).convert("RGB")

            # Detect lines
            lines = self.detect_text_lines(image)

            # Recognize each line
            results = []
            for i, line in enumerate(lines):
                logger.debug(f"Recognizing line {i+1}/{len(lines)}")

                text = self.recognize_from_image(line["image"], preprocess=True)

                result = {
                    "text": text,
                    "bbox": line["bbox"],
                    "line_index": i,
                }

                if return_confidence:
                    # Simple confidence based on text length and content
                    confidence = self._estimate_confidence(text)
                    result["confidence"] = confidence

                results.append(result)

            logger.info(f"Recognized {len(results)} lines from {image_path}")
            return results

        except Exception as e:
            logger.error(f"Error recognizing lines from {image_path}: {e}")
            return []

    def _estimate_confidence(self, text: str) -> float:
        """
        Estimate confidence of recognition result.
        
        Args:
            text: Recognized text
            
        Returns:
            Confidence score (0-1)
        """
        if not text:
            return 0.0

        # Factors that indicate good recognition
        score = 0.5  # Base score

        # Longer text tends to be more reliable
        if len(text) > 10:
            score += 0.1
        if len(text) > 20:
            score += 0.1

        # Text with alphanumeric characters is more reliable
        if any(c.isalnum() for c in text):
            score += 0.1

        # Text with spaces (words) is more reliable
        if " " in text:
            score += 0.1

        # Penalize if too many special characters
        special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
        if special_chars / len(text) > 0.5:
            score -= 0.2

        return max(0.0, min(1.0, score))

    def recognize_from_file(
        self,
        image_path: str,
        mode: str = "full",
    ) -> dict[str, Any]:
        """
        Recognize handwriting from an image file.
        
        Args:
            image_path: Path to image file
            mode: Recognition mode
                - 'full': Recognize entire image as one block
                - 'lines': Detect and recognize individual lines
                
        Returns:
            Dictionary with recognized text and metadata
        """
        try:
            if mode == "full":
                # Recognize entire image
                image = Image.open(image_path).convert("RGB")
                text = self.recognize_from_image(image, preprocess=True)

                return {
                    "text": text,
                    "mode": "full",
                    "confidence": self._estimate_confidence(text),
                }

            elif mode == "lines":
                # Recognize line by line
                lines = self.recognize_lines(image_path, return_confidence=True)

                # Combine all lines
                full_text = "\n".join(line["text"] for line in lines)
                avg_confidence = np.mean([line["confidence"] for line in lines]) if lines else 0.0

                return {
                    "text": full_text,
                    "lines": lines,
                    "mode": "lines",
                    "confidence": float(avg_confidence),
                }

            else:
                raise ValueError(f"Invalid mode: {mode}. Use 'full' or 'lines'")

        except Exception as e:
            logger.error(f"Error recognizing from file {image_path}: {e}")
            return {
                "text": "",
                "mode": mode,
                "confidence": 0.0,
                "error": str(e),
            }

    def recognize_form_fields(
        self,
        image_path: str,
        field_regions: list[dict[str, Any]],
    ) -> dict[str, str]:
        """
        Recognize text from specific form fields.
        
        Args:
            image_path: Path to form image
            field_regions: List of field definitions
                [
                    {
                        'name': 'field_name',
                        'bbox': [x1, y1, x2, y2]
                    },
                    ...
                ]
                
        Returns:
            Dictionary mapping field names to recognized text
        """
        try:
            # Load image
            image = Image.open(image_path).convert("RGB")

            # Extract and recognize each field
            results = {}
            for field in field_regions:
                name = field["name"]
                bbox = field["bbox"]

                # Crop field region
                x1, y1, x2, y2 = bbox
                field_image = image.crop((x1, y1, x2, y2))

                # Recognize text
                text = self.recognize_from_image(field_image, preprocess=True)
                results[name] = text.strip()

                logger.debug(f"Field '{name}': {text[:50]}...")

            return results

        except Exception as e:
            logger.error(f"Error recognizing form fields: {e}")
            return {}

    def batch_recognize(
        self,
        image_paths: list[str],
        mode: str = "full",
    ) -> list[dict[str, Any]]:
        """
        Recognize handwriting from multiple images in batch.
        
        Args:
            image_paths: List of image file paths
            mode: Recognition mode ('full' or 'lines')
            
        Returns:
            List of recognition results
        """
        results = []
        for i, path in enumerate(image_paths):
            logger.info(f"Processing image {i+1}/{len(image_paths)}: {path}")
            result = self.recognize_from_file(path, mode=mode)
            result["image_path"] = path
            results.append(result)

        return results
