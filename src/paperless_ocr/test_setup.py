#!/usr/bin/env python
"""
Script de test pour le module OCR hybride Paperless-ngx
"""

import os
import sys
import django
from pathlib import Path

# Configuration de Django pour utiliser les modèles
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')
sys.path.append('/usr/src/paperless/paperless-ngx/src')

django.setup()

from paperless_ocr.models import OCRConfiguration
from paperless_ocr.config import get_default_ocr_config, DEFAULT_OCR_CONFIG
from paperless_ocr.engines import TesseractEngine, OCRConfig

def test_configuration():
    """Test de la configuration par défaut"""
    print("=== Test de Configuration ===")

    try:
        config = get_default_ocr_config()
        print(f"✅ Configuration par défaut créée")
        print(f"   - Langue Tesseract: {config.tesseract_lang}")
        print(f"   - DPI: {config.dpi}")
        print(f"   - Amélioration d'image: {config.enhance_image}")

        # Test de création d'un objet de configuration en base
        ocr_config, created = OCRConfiguration.objects.get_or_create(
            name="Configuration Test",
            defaults={
                'tesseract_lang': config.tesseract_lang,
                'tesseract_oem': config.tesseract_oem,
                'tesseract_psm': config.tesseract_psm,
                'dpi': config.dpi,
                'enhance_image': config.enhance_image,
                'denoise': config.denoise,
                'is_active': True,
            }
        )

        if created:
            print(f"✅ Configuration sauvée en base (ID: {ocr_config.id})")
        else:
            print(f"✅ Configuration existante trouvée (ID: {ocr_config.id})")

        return True

    except Exception as e:
        print(f"❌ Erreur de configuration: {e}")
        return False

def test_tesseract_availability():
    """Test de disponibilité de Tesseract"""
    print("\n=== Test de Tesseract ===")

    try:
        import pytesseract

        # Test de base
        version = pytesseract.get_tesseract_version()
        print(f"✅ PyTesseract disponible")
        print(f"   - Version: {version}")

        # Test des langues
        langs = pytesseract.get_languages(config='')
        print(f"   - Langues disponibles: {', '.join(langs)}")

        # Test d'un moteur simple
        config = OCRConfig(tesseract_lang='eng')
        engine = TesseractEngine(config)
        print(f"✅ Moteur Tesseract initialisé")

        return True

    except ImportError as e:
        print(f"❌ PyTesseract non disponible: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur Tesseract: {e}")
        return False

def test_opencv_availability():
    """Test de disponibilité d'OpenCV"""
    print("\n=== Test d'OpenCV ===")

    try:
        import cv2
        print(f"✅ OpenCV disponible")
        print(f"   - Version: {cv2.__version__}")
        return True

    except ImportError as e:
        print(f"❌ OpenCV non disponible: {e}")
        return False

def test_models():
    """Test des modèles Django"""
    print("\n=== Test des Modèles ===")

    try:
        from paperless_ocr.models import OCRConfiguration, OCRResult, OCRQueue

        # Test de comptage
        configs = OCRConfiguration.objects.count()
        results = OCRResult.objects.count()
        queue = OCRQueue.objects.count()

        print(f"✅ Modèles disponibles")
        print(f"   - Configurations: {configs}")
        print(f"   - Résultats: {results}")
        print(f"   - Queue: {queue}")

        return True

    except Exception as e:
        print(f"❌ Erreur modèles: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🔍 Test du module OCR hybride Paperless-ngx\n")

    results = []

    # Tests
    results.append(test_configuration())
    results.append(test_tesseract_availability())
    results.append(test_opencv_availability())
    results.append(test_models())

    # Résumé
    print("\n" + "="*50)
    print("RÉSUMÉ DES TESTS")
    print("="*50)

    passed = sum(results)
    total = len(results)

    print(f"Tests réussis: {passed}/{total}")

    if passed == total:
        print("🎉 Tous les tests sont passés !")
        print("\nLe module OCR hybride est prêt à être utilisé.")
    else:
        print("⚠️  Certains tests ont échoué.")
        print("Vérifiez les dépendances et la configuration.")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
