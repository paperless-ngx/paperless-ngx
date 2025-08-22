"""
Configuration par défaut pour le module OCR hybride Paperless-ngx
"""

from django.conf import settings
from .engines import OCRConfig

# Configuration par défaut pour le module OCR
DEFAULT_OCR_CONFIG = {
    # Configuration Tesseract
    'TESSERACT_CMD': getattr(settings, 'TESSERACT_CMD', '/usr/bin/tesseract'),
    'TESSERACT_LANGUAGE': 'fra+eng',  # Français + Anglais
    'TESSERACT_OEM': 3,  # LSTM OCR Engine Mode
    'TESSERACT_PSM': 6,  # Assume uniform block of text

    # Configuration DocTR
    'DOCTR_MODEL': 'db_resnet50',
    'DOCTR_RECOGNITION_MODEL': 'crnn_vgg16_bn',
    'DOCTR_ASSUME_STRAIGHT_PAGES': True,
    'DOCTR_DETECT_ORIENTATION': True,

    # Configuration générale
    'DEFAULT_DPI': 300,
    'MAX_IMAGE_SIZE': 3000,
    'ENHANCE_IMAGE': True,
    'DENOISE': True,

    # Configuration hybride
    'CONFIDENCE_THRESHOLD': 0.7,
    'FUSION_WEIGHTS': {'tesseract': 0.3, 'doctr': 0.7},
    'AUTO_HYBRID_FALLBACK': True,

    # Paramètres de performance
    'ENABLE_BACKGROUND_PROCESSING': True,
    'MAX_CONCURRENT_TASKS': 2,
    'TASK_TIMEOUT': 300,  # 5 minutes
}

def get_default_ocr_config():
    """Retourne une configuration OCR par défaut"""
    return OCRConfig(
        # Tesseract
        tesseract_lang=DEFAULT_OCR_CONFIG['TESSERACT_LANGUAGE'],
        tesseract_oem=DEFAULT_OCR_CONFIG['TESSERACT_OEM'],
        tesseract_psm=DEFAULT_OCR_CONFIG['TESSERACT_PSM'],

        # DocTR
        doctr_model=DEFAULT_OCR_CONFIG['DOCTR_MODEL'],
        doctr_recognition_model=DEFAULT_OCR_CONFIG['DOCTR_RECOGNITION_MODEL'],
        doctr_assume_straight_pages=DEFAULT_OCR_CONFIG['DOCTR_ASSUME_STRAIGHT_PAGES'],
        doctr_detect_orientation=DEFAULT_OCR_CONFIG['DOCTR_DETECT_ORIENTATION'],

        # Traitement d'image
        dpi=DEFAULT_OCR_CONFIG['DEFAULT_DPI'],
        max_image_size=DEFAULT_OCR_CONFIG['MAX_IMAGE_SIZE'],
        enhance_image=DEFAULT_OCR_CONFIG['ENHANCE_IMAGE'],
        denoise=DEFAULT_OCR_CONFIG['DENOISE'],
    )
