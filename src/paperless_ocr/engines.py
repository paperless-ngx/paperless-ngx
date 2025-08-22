import abc
import io
import os
import tempfile
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
from PIL import Image, ImageEnhance
import fitz  # PyMuPDF
import numpy as np
from dataclasses import dataclass

# Import optionnel d'OpenCV
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    cv2 = None

# Import optionnel de PyTesseract
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    pytesseract = None

# Import optionnel de DocTR
try:
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
    HAS_DOCTR = True
except ImportError:
    HAS_DOCTR = False
    DocumentFile = None
    ocr_predictor = None

from django.conf import settings
from documents.models import Document

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Structure pour stocker les résultats OCR"""
    text: str
    confidence: float
    processing_time: float
    metadata: Dict = None
    bounding_boxes: List = None
    page_results: List = None


@dataclass
class OCRConfig:
    """Configuration pour les moteurs OCR"""
    # Tesseract
    tesseract_lang: str = 'fra+eng'
    tesseract_psm: int = 6
    tesseract_oem: int = 3
    tesseract_config: str = '--psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,;:!?-()[]'

    # Doctr
    doctr_model: str = 'db_resnet50'
    doctr_recognition_model: str = 'crnn_vgg16_bn'
    doctr_assume_straight_pages: bool = True
    doctr_detect_orientation: bool = True

    # Processing
    max_image_size: int = 3000
    dpi: int = 300
    enhance_image: bool = True
    denoise: bool = True

    # Performance
    max_memory_mb: int = 1024
    batch_size: int = 4


class OCREngine(abc.ABC):
    """Classe de base abstraite pour les moteurs OCR"""

    def __init__(self, config: OCRConfig = None):
        self.config = config or OCRConfig()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abc.abstractmethod
    def process(self, document: Document) -> OCRResult:
        """Traite un document et retourne le résultat OCR"""
        raise NotImplementedError

    def _get_document_images(self, document: Document) -> List[Image.Image]:
        """Convertit un document en images PIL"""
        images = []

        try:
            if document.mime_type == "application/pdf":
                images = self._pdf_to_images(document.source_path)
            elif document.mime_type.startswith("image/"):
                image = Image.open(document.source_path)
                images = [image]
            else:
                raise ValueError(f"Format non supporté: {document.mime_type}")

        except Exception as e:
            self.logger.error(f"Erreur conversion document {document.id}: {e}")
            raise

        return images

    def _pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """Convertit un PDF en images"""
        images = []

        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                mat = fitz.Matrix(self.config.dpi / 72, self.config.dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("ppm")
                image = Image.open(io.BytesIO(img_data))
                images.append(image)
            doc.close()

        except Exception as e:
            self.logger.error(f"Erreur conversion PDF: {e}")
            raise

        return images

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Préprocessing de l'image pour améliorer l'OCR"""
        try:
            # Conversion en numpy array
            img_array = np.array(image)

            # Redimensionnement si nécessaire
            height, width = img_array.shape[:2]
            if max(height, width) > self.config.max_image_size:
                scale = self.config.max_image_size / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)

                if HAS_OPENCV and cv2 is not None:
                    img_array = cv2.resize(img_array, (new_width, new_height))
                else:
                    # Fallback sans OpenCV
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    img_array = np.array(image)

            if self.config.enhance_image and HAS_OPENCV and cv2 is not None:
                # Conversion en niveaux de gris si nécessaire
                if len(img_array.shape) == 3:
                    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                else:
                    gray = img_array

                # Amélioration du contraste
                gray = cv2.equalizeHist(gray)

                # Débruitage
                if self.config.denoise:
                    gray = cv2.fastNlMeansDenoising(gray)

                # Binarisation adaptative
                img_array = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                )
                return Image.fromarray(img_array)

            elif self.config.enhance_image:
                # Fallback simple sans OpenCV
                image = image.convert('L')  # Conversion en niveaux de gris
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.5)  # Amélioration du contraste
                return image

            # Conversion back en PIL
            return Image.fromarray(img_array)

        except Exception as e:
            self.logger.warning(f"Erreur préprocessing: {e}, utilisation image originale")
            return image


class TesseractEngine(OCREngine):
    """Moteur OCR Tesseract - rapide mais moins précis"""

    def __init__(self, config: OCRConfig = None):
        super().__init__(config)
        if HAS_TESSERACT:
            self._configure_tesseract()
        else:
            raise ImportError("PyTesseract n'est pas disponible. Installez-le avec: pip install pytesseract")

    def _configure_tesseract(self):
        """Configure Tesseract selon les paramètres"""
        # Configuration du chemin Tesseract si spécifié
        tesseract_cmd = getattr(settings, 'TESSERACT_CMD', None)
        if tesseract_cmd and pytesseract:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def process(self, document: Document) -> OCRResult:
        """Traite un document avec Tesseract"""
        start_time = time.time()

        try:
            images = self._get_document_images(document)
            all_text = []
            all_confidences = []
            page_results = []

            for page_idx, image in enumerate(images):
                # Préprocessing
                processed_image = self._preprocess_image(image)

                # Configuration Tesseract
                custom_config = f'--oem {self.config.tesseract_oem} --psm {self.config.tesseract_psm}'

                # Extraction du texte
                try:
                    if not pytesseract:
                        raise ImportError("PyTesseract non disponible")

                    text = pytesseract.image_to_string(
                        processed_image,
                        lang=self.config.tesseract_lang,
                        config=custom_config
                    )

                    # Extraction des données détaillées pour la confiance
                    data = pytesseract.image_to_data(
                        processed_image,
                        lang=self.config.tesseract_lang,
                        config=custom_config,
                        output_type=pytesseract.Output.DICT
                    )

                    # Calcul de la confiance moyenne
                    confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                    page_confidence = np.mean(confidences) / 100.0 if confidences else 0.0

                    all_text.append(text)
                    all_confidences.append(page_confidence)

                    page_results.append({
                        'page': page_idx + 1,
                        'text': text,
                        'confidence': page_confidence,
                        'word_count': len(text.split())
                    })

                except Exception as e:
                    self.logger.error(f"Erreur Tesseract page {page_idx}: {e}")
                    page_results.append({
                        'page': page_idx + 1,
                        'text': '',
                        'confidence': 0.0,
                        'error': str(e)
                    })

            # Fusion des résultats
            final_text = '\n\n'.join(all_text)
            final_confidence = np.mean(all_confidences) if all_confidences else 0.0
            processing_time = time.time() - start_time

            return OCRResult(
                text=final_text,
                confidence=final_confidence,
                processing_time=processing_time,
                page_results=page_results,
                metadata={
                    'engine': 'tesseract',
                    'lang': self.config.tesseract_lang,
                    'psm': self.config.tesseract_psm,
                    'pages_processed': len(images)
                }
            )

        except Exception as e:
            self.logger.error(f"Erreur Tesseract document {document.id}: {e}")
            return OCRResult(
                text='',
                confidence=0.0,
                processing_time=time.time() - start_time,
                metadata={'error': str(e)}
            )


class DoctrEngine(OCREngine):
    """Moteur OCR Doctr - plus précis mais plus lent"""

    def __init__(self, config: OCRConfig = None):
        super().__init__(config)
        if not HAS_DOCTR:
            raise ImportError("DocTR n'est pas disponible. Installez-le avec: pip install python-doctr")
        self.model = None
        self._load_model()

    def _load_model(self):
        """Charge le modèle Doctr"""
        try:
            if not ocr_predictor:
                raise ImportError("DocTR non disponible")

            self.model = ocr_predictor(
                det_arch=self.config.doctr_model,
                reco_arch=self.config.doctr_recognition_model,
                pretrained=True,
                assume_straight_pages=self.config.doctr_assume_straight_pages,
                detect_orientation=self.config.doctr_detect_orientation
            )
            self.logger.info("Modèle Doctr chargé avec succès")

        except Exception as e:
            self.logger.error(f"Erreur chargement modèle Doctr: {e}")
            raise

    def process(self, document: Document) -> OCRResult:
        """Traite un document avec Doctr"""
        start_time = time.time()

        try:
            if not self.model:
                self._load_model()

            # Traitement avec Doctr
            if not DocumentFile:
                raise ImportError("DocumentFile non disponible")

            if document.mime_type == "application/pdf":
                doc_file = DocumentFile.from_pdf(document.source_path)
            else:
                doc_file = DocumentFile.from_images(document.source_path)

            # Prédiction
            result = self.model(doc_file)

            # Extraction du texte et des confidences
            all_text = []
            all_confidences = []
            page_results = []

            for page_idx, page in enumerate(result.pages):
                page_text = []
                page_confidences = []

                for block in page.blocks:
                    for line in block.lines:
                        line_text = []
                        line_confidences = []

                        for word in line.words:
                            line_text.append(word.value)
                            line_confidences.append(word.confidence)

                        if line_text:
                            page_text.append(' '.join(line_text))
                            page_confidences.extend(line_confidences)

                page_full_text = '\n'.join(page_text)
                page_confidence = np.mean(page_confidences) if page_confidences else 0.0

                all_text.append(page_full_text)
                all_confidences.append(page_confidence)

                page_results.append({
                    'page': page_idx + 1,
                    'text': page_full_text,
                    'confidence': page_confidence,
                    'word_count': len(page_full_text.split()),
                    'blocks': len(page.blocks),
                    'lines': sum(len(block.lines) for block in page.blocks)
                })

            # Fusion des résultats
            final_text = '\n\n'.join(all_text)
            final_confidence = np.mean(all_confidences) if all_confidences else 0.0
            processing_time = time.time() - start_time

            return OCRResult(
                text=final_text,
                confidence=final_confidence,
                processing_time=processing_time,
                page_results=page_results,
                metadata={
                    'engine': 'doctr',
                    'model': self.config.doctr_model,
                    'recognition_model': self.config.doctr_recognition_model,
                    'pages_processed': len(result.pages)
                }
            )

        except Exception as e:
            self.logger.error(f"Erreur Doctr document {document.id}: {e}")
            return OCRResult(
                text='',
                confidence=0.0,
                processing_time=time.time() - start_time,
                metadata={'error': str(e)}
            )


class HybridEngine:
    """Moteur de fusion intelligent des résultats OCR"""

    def __init__(self, config: OCRConfig = None):
        self.config = config or OCRConfig()
        self.logger = logging.getLogger(f"{__name__.HybridEngine}")

    def fuse(self, tesseract_result: OCRResult, doctr_result: OCRResult) -> OCRResult:
        """Fusionne les résultats de Tesseract et Doctr intelligemment"""

        try:
            # Stratégies de fusion
            fusion_strategies = [
                self._confidence_based_fusion,
                self._length_based_fusion,
                self._word_similarity_fusion,
                self._hybrid_page_fusion
            ]

            best_result = None
            best_score = 0.0

            for strategy in fusion_strategies:
                try:
                    result = strategy(tesseract_result, doctr_result)
                    score = self._evaluate_fusion_quality(result, tesseract_result, doctr_result)

                    if score > best_score:
                        best_score = score
                        best_result = result

                except Exception as e:
                    self.logger.warning(f"Erreur stratégie fusion: {e}")
                    continue

            if best_result is None:
                # Fallback: prendre le meilleur résultat individuel
                if tesseract_result.confidence > doctr_result.confidence:
                    best_result = tesseract_result
                else:
                    best_result = doctr_result

            # Ajout métadonnées de fusion
            best_result.metadata = best_result.metadata or {}
            best_result.metadata.update({
                'fusion_engine': 'hybrid',
                'fusion_score': best_score,
                'tesseract_confidence': tesseract_result.confidence,
                'doctr_confidence': doctr_result.confidence,
                'tesseract_length': len(tesseract_result.text),
                'doctr_length': len(doctr_result.text)
            })

            return best_result

        except Exception as e:
            self.logger.error(f"Erreur fusion hybride: {e}")
            # Fallback sur le meilleur résultat individuel
            if tesseract_result.confidence > doctr_result.confidence:
                return tesseract_result
            else:
                return doctr_result

    def _confidence_based_fusion(self, tesseract_result: OCRResult, doctr_result: OCRResult) -> OCRResult:
        """Fusion basée sur la confiance globale"""
        if tesseract_result.confidence > doctr_result.confidence:
            winner = tesseract_result
        else:
            winner = doctr_result

        return OCRResult(
            text=winner.text,
            confidence=winner.confidence,
            processing_time=tesseract_result.processing_time + doctr_result.processing_time,
            metadata={'fusion_method': 'confidence_based', 'winner': winner.metadata.get('engine')}
        )

    def _length_based_fusion(self, tesseract_result: OCRResult, doctr_result: OCRResult) -> OCRResult:
        """Fusion basée sur la longueur du texte (plus long = probablement plus complet)"""
        if len(tesseract_result.text) > len(doctr_result.text):
            winner = tesseract_result
        else:
            winner = doctr_result

        return OCRResult(
            text=winner.text,
            confidence=(tesseract_result.confidence + doctr_result.confidence) / 2,
            processing_time=tesseract_result.processing_time + doctr_result.processing_time,
            metadata={'fusion_method': 'length_based', 'winner': winner.metadata.get('engine')}
        )

    def _word_similarity_fusion(self, tesseract_result: OCRResult, doctr_result: OCRResult) -> OCRResult:
        """Fusion basée sur la similarité des mots"""
        from difflib import SequenceMatcher

        # Calculer la similarité
        similarity = SequenceMatcher(None, tesseract_result.text, doctr_result.text).ratio()

        # Si très similaire, prendre la version avec le plus de confiance
        if similarity > 0.8:
            if tesseract_result.confidence > doctr_result.confidence:
                winner = tesseract_result
            else:
                winner = doctr_result
        else:
            # Si différent, prendre la version la plus longue
            if len(tesseract_result.text) > len(doctr_result.text):
                winner = tesseract_result
            else:
                winner = doctr_result

        return OCRResult(
            text=winner.text,
            confidence=winner.confidence * (1 + similarity) / 2,  # Bonus pour similarité
            processing_time=tesseract_result.processing_time + doctr_result.processing_time,
            metadata={
                'fusion_method': 'similarity_based',
                'similarity_score': similarity,
                'winner': winner.metadata.get('engine')
            }
        )

    def _hybrid_page_fusion(self, tesseract_result: OCRResult, doctr_result: OCRResult) -> OCRResult:
        """Fusion page par page en choisissant le meilleur résultat pour chaque page"""
        if not (tesseract_result.page_results and doctr_result.page_results):
            return self._confidence_based_fusion(tesseract_result, doctr_result)

        fused_pages = []
        fused_text = []
        total_confidence = []

        max_pages = max(len(tesseract_result.page_results), len(doctr_result.page_results))

        for page_idx in range(max_pages):
            tess_page = tesseract_result.page_results[page_idx] if page_idx < len(tesseract_result.page_results) else None
            doctr_page = doctr_result.page_results[page_idx] if page_idx < len(doctr_result.page_results) else None

            if tess_page and doctr_page:
                # Choisir la page avec la meilleure confiance
                if tess_page['confidence'] > doctr_page['confidence']:
                    winner_page = tess_page
                    winner_engine = 'tesseract'
                else:
                    winner_page = doctr_page
                    winner_engine = 'doctr'

                fused_pages.append({
                    **winner_page,
                    'fusion_winner': winner_engine,
                    'tesseract_confidence': tess_page['confidence'],
                    'doctr_confidence': doctr_page['confidence']
                })

            elif tess_page:
                fused_pages.append({**tess_page, 'fusion_winner': 'tesseract'})
            elif doctr_page:
                fused_pages.append({**doctr_page, 'fusion_winner': 'doctr'})

            if fused_pages:
                fused_text.append(fused_pages[-1]['text'])
                total_confidence.append(fused_pages[-1]['confidence'])

        return OCRResult(
            text='\n\n'.join(fused_text),
            confidence=np.mean(total_confidence) if total_confidence else 0.0,
            processing_time=tesseract_result.processing_time + doctr_result.processing_time,
            page_results=fused_pages,
            metadata={'fusion_method': 'hybrid_page_fusion'}
        )

    def _evaluate_fusion_quality(self, result: OCRResult, tesseract_result: OCRResult, doctr_result: OCRResult) -> float:
        """Évalue la qualité d'un résultat de fusion"""
        score = 0.0

        # Facteur confiance (40%)
        score += result.confidence * 0.4

        # Facteur longueur (30%)
        max_length = max(len(tesseract_result.text), len(doctr_result.text))
        if max_length > 0:
            length_score = len(result.text) / max_length
            score += min(length_score, 1.0) * 0.3

        # Facteur cohérence (30%)
        # Vérifier que le texte contient des mots valides
        words = result.text.split()
        if words:
            # Pourcentage de "mots" qui contiennent au moins une lettre
            valid_words = sum(1 for word in words if any(c.isalpha() for c in word))
            coherence_score = valid_words / len(words)
            score += coherence_score * 0.3

        return score
