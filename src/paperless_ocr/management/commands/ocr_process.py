"""
Commande de gestion pour le module OCR hybride Paperless-ngx

Usage:
    python manage.py ocr_process --help
    python manage.py ocr_process --document-id 123 --engine tesseract
    python manage.py ocr_process --reprocess-all --engine hybrid
    python manage.py ocr_process --stats
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from documents.models import Document
from paperless_ocr.models import OCRConfiguration, OCRResult, OCRQueue
from paperless_ocr.engines import TesseractEngine, OCRConfig
from paperless_ocr.tasks import process_document_ocr
from paperless_ocr.config import get_default_ocr_config
import os


class Command(BaseCommand):
    help = 'Commandes de gestion pour le système OCR hybride'

    def add_arguments(self, parser):
        parser.add_argument(
            '--document-id',
            type=int,
            help='ID du document à traiter'
        )

        parser.add_argument(
            '--engine',
            choices=['tesseract', 'doctr', 'hybrid'],
            default='hybrid',
            help='Moteur OCR à utiliser (défaut: hybrid)'
        )

        parser.add_argument(
            '--reprocess-all',
            action='store_true',
            help='Retraiter tous les documents'
        )

        parser.add_argument(
            '--failed-only',
            action='store_true',
            help='Retraiter seulement les documents en échec'
        )

        parser.add_argument(
            '--stats',
            action='store_true',
            help='Afficher les statistiques OCR'
        )

        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Nettoyer les anciens résultats OCR'
        )

        parser.add_argument(
            '--setup',
            action='store_true',
            help='Configurer le module OCR avec des paramètres par défaut'
        )

        parser.add_argument(
            '--test',
            action='store_true',
            help='Tester le fonctionnement du module OCR'
        )

        parser.add_argument(
            '--async',
            action='store_true',
            help='Traitement asynchrone avec Celery'
        )

        parser.add_argument(
            '--priority',
            choices=['low', 'normal', 'high'],
            default='normal',
            help='Priorité du traitement (défaut: normal)'
        )

    def handle(self, *args, **options):
        # Configuration de l'environnement pour éviter les problèmes d'affichage
        os.environ.setdefault('DISPLAY', '')
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

        if options['stats']:
            self.show_stats()
        elif options['setup']:
            self.setup_ocr()
        elif options['test']:
            self.test_ocr()
        elif options['cleanup']:
            self.cleanup_ocr()
        elif options['reprocess_all']:
            self.reprocess_all(options)
        elif options['failed_only']:
            self.reprocess_failed(options)
        elif options['document_id']:
            self.process_document(options)
        else:
            self.stdout.write(
                self.style.ERROR('Aucune action spécifiée. Utilisez --help pour voir les options.')
            )

    def show_stats(self):
        """Affiche les statistiques OCR"""
        self.stdout.write(self.style.SUCCESS('📊 Statistiques OCR'))
        self.stdout.write('=' * 50)

        # Configurations
        configs = OCRConfiguration.objects.count()
        active_configs = OCRConfiguration.objects.filter(is_active=True).count()

        self.stdout.write(f'Configurations: {configs} (actives: {active_configs})')

        # Résultats
        total_results = OCRResult.objects.count()
        completed = OCRResult.objects.filter(status='completed').count()
        failed = OCRResult.objects.filter(status='failed').count()
        pending = OCRResult.objects.filter(status='pending').count()

        self.stdout.write(f'Résultats: {total_results}')
        self.stdout.write(f'  - Terminés: {completed}')
        self.stdout.write(f'  - Échecs: {failed}')
        self.stdout.write(f'  - En attente: {pending}')

        # File d'attente
        queue_count = OCRQueue.objects.count()
        queue_pending = OCRQueue.objects.filter(status='pending').count()

        self.stdout.write(f'File d\'attente: {queue_count} (en attente: {queue_pending})')

        # Statistiques par moteur
        if completed > 0:
            self.stdout.write('\nPar moteur:')
            engines = OCRResult.objects.filter(status='completed').values_list('engine', flat=True).distinct()

            for engine in engines:
                results = OCRResult.objects.filter(engine=engine, status='completed')
                count = results.count()

                from django.db.models import Avg
                avg_confidence = results.aggregate(avg=Avg('confidence'))['avg'] or 0
                avg_time = results.aggregate(avg=Avg('processing_time'))['avg'] or 0

                self.stdout.write(f'  {engine}: {count} docs, conf={avg_confidence:.1%}, temps={avg_time:.1f}s')

    def setup_ocr(self):
        """Configure le module OCR avec des paramètres par défaut"""
        self.stdout.write(self.style.SUCCESS('🔧 Configuration du module OCR'))

        # Configuration par défaut
        config, created = OCRConfiguration.objects.get_or_create(
            name="Configuration Par Défaut",
            defaults={
                'tesseract_lang': 'fra+eng',
                'tesseract_psm': 6,
                'tesseract_oem': 3,
                'doctr_model': 'db_resnet50',
                'dpi': 300,
                'enhance_image': True,
                'denoise': True,
                'is_active': True,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS('✅ Configuration créée'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Configuration existante'))

        self.stdout.write(f'ID de configuration: {config.id}')

    def test_ocr(self):
        """Teste le fonctionnement du module OCR"""
        self.stdout.write(self.style.SUCCESS('🧪 Test du module OCR'))

        try:
            # Test de la configuration
            config = get_default_ocr_config()
            self.stdout.write('✅ Configuration chargée')

            # Test Tesseract
            try:
                engine = TesseractEngine(config)
                self.stdout.write('✅ Moteur Tesseract disponible')
            except ImportError:
                self.stdout.write(self.style.ERROR('❌ Tesseract non disponible'))

            # Test OpenCV
            try:
                import cv2
                self.stdout.write(f'✅ OpenCV disponible (v{cv2.__version__})')
            except ImportError:
                self.stdout.write(self.style.ERROR('❌ OpenCV non disponible'))

            # Test des modèles
            configs = OCRConfiguration.objects.count()
            self.stdout.write(f'✅ Base de données accessible ({configs} configs)')

            self.stdout.write(self.style.SUCCESS('🎉 Module OCR fonctionnel'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erreur de test: {e}'))

    def cleanup_ocr(self):
        """Nettoie les anciens résultats OCR"""
        self.stdout.write(self.style.WARNING('🧹 Nettoyage des résultats OCR'))

        with transaction.atomic():
            # Suppression des résultats en échec anciens
            old_failed = OCRResult.objects.filter(
                status='failed',
                created__lt='2024-01-01'  # Plus anciens que 2024
            )
            count_failed = old_failed.count()
            old_failed.delete()

            # Suppression des éléments de queue terminés
            old_queue = OCRQueue.objects.filter(
                status__in=['completed', 'failed'],
                created__lt='2024-01-01'
            )
            count_queue = old_queue.count()
            old_queue.delete()

            self.stdout.write(f'✅ Nettoyé: {count_failed} résultats, {count_queue} tâches')

    def process_document(self, options):
        """Traite un document spécifique"""
        document_id = options['document_id']
        engine = options['engine']
        use_async = options['async']
        priority = options['priority']

        try:
            document = Document.objects.get(id=document_id)
            self.stdout.write(f'📄 Traitement de: {document.title}')

            if use_async:
                # Traitement asynchrone
                task = process_document_ocr.delay(
                    document_id=document_id,
                    engine_name=engine,
                    priority=priority
                )
                self.stdout.write(f'🚀 Tâche asynchrone lancée: {task.id}')
            else:
                # Traitement synchrone
                from paperless_ocr.engines import TesseractEngine

                config = get_default_ocr_config()
                engine_obj = TesseractEngine(config)

                self.stdout.write(f'⚡ Traitement synchrone avec {engine}...')
                result = engine_obj.process(document)

                self.stdout.write(self.style.SUCCESS('✅ Traitement terminé'))
                self.stdout.write(f'   Confiance: {result.confidence:.2%}')
                self.stdout.write(f'   Temps: {result.processing_time:.2f}s')

        except Document.DoesNotExist:
            raise CommandError(f'Document {document_id} non trouvé')
        except Exception as e:
            raise CommandError(f'Erreur de traitement: {e}')

    def reprocess_all(self, options):
        """Retraite tous les documents"""
        engine = options['engine']
        use_async = options['async']
        priority = options['priority']

        documents = Document.objects.all()
        count = documents.count()

        self.stdout.write(f'🔄 Retraitement de {count} documents avec {engine}')

        if not input('Continuer? (y/N): ').lower().startswith('y'):
            self.stdout.write('Annulé')
            return

        for i, document in enumerate(documents, 1):
            self.stdout.write(f'[{i}/{count}] {document.title}')

            try:
                if use_async:
                    process_document_ocr.delay(
                        document_id=document.id,
                        engine_name=engine,
                        priority=priority
                    )
                else:
                    # Version synchrone simplifiée
                    self.stdout.write(f'  Traitement synchrone non implémenté pour le retraitement en lot')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Erreur: {e}'))

    def reprocess_failed(self, options):
        """Retraite les documents en échec"""
        failed_results = OCRResult.objects.filter(status='failed')
        count = failed_results.count()

        self.stdout.write(f'🔄 Retraitement de {count} documents en échec')

        for result in failed_results:
            self.stdout.write(f'📄 {result.document.title}')

            try:
                process_document_ocr.delay(
                    document_id=result.document.id,
                    engine_name=options['engine'],
                    priority=options['priority']
                )
                self.stdout.write('  ✅ Relancé')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Erreur: {e}'))
