#!/usr/bin/env python
"""
Exemple d'utilisation du module OCR hybride Paperless-ngx

Ce script montre comment utiliser le module OCR pour traiter des documents
et comparer les différents moteurs.
"""

import os
import sys
import django
from pathlib import Path

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')
sys.path.append('/usr/src/paperless/paperless-ngx/src')

django.setup()

from documents.models import Document
from paperless_ocr.models import OCRConfiguration, OCRResult
from paperless_ocr.engines import TesseractEngine, OCRConfig
from paperless_ocr.tasks import process_document_ocr
from paperless_ocr.config import get_default_ocr_config

def demo_configuration():
    """Démonstration de création de configuration"""
    print("🔧 Création de configuration OCR")

    # Configuration pour documents français
    config_fr, created = OCRConfiguration.objects.get_or_create(
        name="Français Haute Qualité",
        defaults={
            'tesseract_lang': 'fra',
            'tesseract_psm': 6,  # Bloc de texte uniforme
            'tesseract_oem': 3,  # LSTM
            'doctr_model': 'db_resnet50',
            'dpi': 300,
            'enhance_image': True,
            'denoise': True,
            'is_active': True,
        }
    )

    # Configuration pour documents mixtes
    config_multi, created = OCRConfiguration.objects.get_or_create(
        name="Multilingue Rapide",
        defaults={
            'tesseract_lang': 'fra+eng+deu',
            'tesseract_psm': 3,  # Auto avec OSD
            'tesseract_oem': 3,
            'dpi': 200,  # Plus rapide
            'enhance_image': False,
            'denoise': False,
            'is_active': False,  # Alternative
        }
    )

    print(f"✅ Configuration '{config_fr.name}' : {'créée' if created else 'existante'}")
    print(f"✅ Configuration '{config_multi.name}' : {'créée' if created else 'existante'}")

    return config_fr

def demo_direct_processing():
    """Démonstration de traitement direct avec les moteurs"""
    print("\n🔍 Traitement direct avec Tesseract")

    # Récupération d'un document (le premier disponible)
    document = Document.objects.first()
    if not document:
        print("❌ Aucun document trouvé dans la base")
        return None

    print(f"📄 Document: {document.title}")
    print(f"   Type: {document.mime_type}")
    print(f"   Taille: {document.size} bytes")

    # Configuration OCR
    config = get_default_ocr_config()

    try:
        # Test avec Tesseract
        engine = TesseractEngine(config)
        print(f"⚡ Traitement avec Tesseract...")

        result = engine.process(document)

        print(f"✅ Traitement terminé")
        print(f"   Confiance: {result.confidence:.2%}")
        print(f"   Temps: {result.processing_time:.2f}s")
        print(f"   Pages: {result.page_count}")
        print(f"   Texte (extrait): {result.text[:100]}...")

        return result

    except ImportError as e:
        print(f"❌ Moteur non disponible: {e}")
        return None
    except Exception as e:
        print(f"❌ Erreur de traitement: {e}")
        return None

def demo_async_processing():
    """Démonstration de traitement asynchrone"""
    print("\n⚡ Traitement asynchrone avec Celery")

    document = Document.objects.first()
    if not document:
        print("❌ Aucun document trouvé")
        return

    print(f"📄 Lancement du traitement pour: {document.title}")

    # Lancement de la tâche asynchrone
    task = process_document_ocr.delay(
        document_id=document.id,
        engine_name="tesseract",
        priority="normal"
    )

    print(f"🚀 Tâche lancée: {task.id}")
    print(f"   Status: {task.status}")

    # Note: En production, on attendrait la completion de la tâche
    print("   (En mode demo, on n'attend pas la completion)")

def demo_results_analysis():
    """Démonstration d'analyse des résultats"""
    print("\n📊 Analyse des résultats OCR")

    # Statistiques générales
    total_results = OCRResult.objects.count()
    completed_results = OCRResult.objects.filter(status='completed').count()

    print(f"📈 Statistiques:")
    print(f"   Total résultats: {total_results}")
    print(f"   Terminés: {completed_results}")

    if completed_results > 0:
        # Analyse par moteur
        engines = OCRResult.objects.filter(status='completed').values_list('engine', flat=True).distinct()

        for engine in engines:
            results = OCRResult.objects.filter(engine=engine, status='completed')
            count = results.count()

            if count > 0:
                avg_confidence = results.aggregate(
                    avg_conf=models.Avg('confidence')
                )['avg_conf'] or 0

                avg_time = results.aggregate(
                    avg_time=models.Avg('processing_time')
                )['avg_time'] or 0

                print(f"   {engine.title()}:")
                print(f"     - Résultats: {count}")
                print(f"     - Confiance moyenne: {avg_confidence:.2%}")
                print(f"     - Temps moyen: {avg_time:.2f}s")

def demo_api_examples():
    """Exemples d'utilisation via API"""
    print("\n🌐 Exemples d'utilisation API")

    print("📝 Commandes curl pour tester les APIs:")

    print("\n1. Déclencher OCR sur un document:")
    print("   curl -X POST http://localhost:8000/api/ocr/documents/1/process/ \\")
    print("        -H 'Content-Type: application/json' \\")
    print("        -d '{\"engine\": \"hybrid\", \"priority\": \"high\"}'")

    print("\n2. Consulter les résultats:")
    print("   curl http://localhost:8000/api/ocr/results/?document=1")

    print("\n3. Statistiques d'un document:")
    print("   curl http://localhost:8000/api/ocr/documents/1/statistics/")

    print("\n4. État de la file d'attente:")
    print("   curl http://localhost:8000/api/ocr/queue/")

def main():
    """Fonction principale de démonstration"""
    print("🚀 Démonstration du module OCR hybride Paperless-ngx")
    print("=" * 60)

    try:
        # 1. Configuration
        config = demo_configuration()

        # 2. Traitement direct
        result = demo_direct_processing()

        # 3. Traitement asynchrone
        demo_async_processing()

        # 4. Analyse des résultats
        demo_results_analysis()

        # 5. Exemples API
        demo_api_examples()

        print("\n" + "="*60)
        print("✅ Démonstration terminée avec succès!")
        print("\n📚 Consultez le README.md pour plus d'informations")
        print("🔧 Interface admin: http://localhost:8000/admin/paperless_ocr/")

    except Exception as e:
        print(f"\n❌ Erreur pendant la démonstration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Ajout des imports nécessaires pour l'analyse
    from django.db import models

    main()
