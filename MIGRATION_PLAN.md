# Plan de Migration - Extension Paperless-ngx

## Table des matières
1. [Vue d'ensemble](#vue-densemble)
2. [Phases de migration](#phases-de-migration)
3. [Prérequis et dépendances](#prérequis-et-dépendances)
4. [Migration des données](#migration-des-données)
5. [Tests et validation](#tests-et-validation)
6. [Rollback et récupération](#rollback-et-récupération)
7. [Monitoring et performance](#monitoring-et-performance)
8. [Timeline et jalons](#timeline-et-jalons)

## Vue d'ensemble

Ce plan détaille la migration progressive de Paperless-ngx vers l'architecture étendue avec fonctionnalités IA. La migration est conçue pour minimiser les interruptions de service et permettre un retour en arrière à tout moment.

### Objectifs de la migration
- **Zéro downtime** : Migration sans interruption de service
- **Compatibilité ascendante** : Préservation de toutes les fonctionnalités existantes
- **Migration progressive** : Activation graduelle des nouvelles fonctionnalités
- **Sécurité des données** : Sauvegarde et vérification d'intégrité à chaque étape

### Stratégie de migration
- **Blue-Green Deployment** : Déploiement parallèle pour tests
- **Feature Flags** : Activation progressive des fonctionnalités
- **Rollback Plan** : Procédures de retour en arrière documentées
- **Monitoring continu** : Surveillance des performances et erreurs

## Phases de migration

### Phase 1 : Préparation et infrastructure (Semaines 1-2)

#### 1.1 Évaluation de l'environnement existant

```bash
#!/bin/bash
# Script d'évaluation pré-migration

echo "=== Évaluation Paperless-ngx Pre-Migration ==="

# Version actuelle
python manage.py --version

# Taille de la base de données
echo "Taille base de données:"
du -sh data/

# Nombre de documents
python manage.py shell -c "
from documents.models import Document
print(f'Documents: {Document.objects.count()}')
print(f'Taille moyenne: {Document.objects.aggregate(avg_size=Avg(\"content__length\"))}')
"

# Utilisation mémoire et CPU
free -h
nproc
df -h

# Dépendances Python actuelles
pip list > requirements_before_migration.txt

# Configuration actuelle
python manage.py diffsettings > settings_before_migration.txt
```

#### 1.2 Sauvegarde complète

```bash
#!/bin/bash
# Script de sauvegarde complète

BACKUP_DIR="/backup/paperless_migration_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "=== Sauvegarde Paperless-ngx ==="

# Sauvegarde base de données
python manage.py document_exporter --data-only "$BACKUP_DIR/database_export.zip"

# Sauvegarde fichiers
tar -czf "$BACKUP_DIR/media_files.tar.gz" media/
tar -czf "$BACKUP_DIR/data_files.tar.gz" data/

# Sauvegarde configuration
cp -r src/paperless/settings.py "$BACKUP_DIR/"
cp -r docker-compose.yml "$BACKUP_DIR/"
cp -r .env "$BACKUP_DIR/"

# Vérification de l'intégrité
python manage.py check
python manage.py sanity_checker

echo "Sauvegarde terminée: $BACKUP_DIR"
```

#### 1.3 Installation des nouvelles dépendances

```bash
#!/bin/bash
# Installation progressive des dépendances IA

# Mise à jour uv.lock avec nouvelles dépendances
cat >> pyproject.toml << EOF

# Dépendances IA Extension
[project.optional-dependencies]
ai = [
    "torch>=2.0.0,<3.0.0",
    "transformers>=4.21.0",
    "sentence-transformers>=2.2.2",
    "doctr[torch]>=0.8.0",
    "faiss-cpu>=1.7.4",
    "chromadb>=0.4.0",
    "spacy>=3.6.0",
    "numpy>=1.24.0",
    "scikit-learn>=1.3.0",
]

ocr = [
    "easyocr>=1.7.0",
    "paddlepaddle>=2.5.0",
    "paddleocr>=2.7.0",
]

calendar = [
    "caldav>=1.3.6",
    "icalendar>=5.0.7",
    "recurring-ical-events>=2.1.2",
]
EOF

# Installation en mode test
uv sync --extra ai --extra ocr --extra calendar
```

#### 1.4 Téléchargement des modèles IA

```python
# management/commands/download_ai_models.py
from django.core.management.base import BaseCommand
from pathlib import Path
import requests
from tqdm import tqdm

class Command(BaseCommand):
    help = 'Télécharge les modèles IA nécessaires'

    def add_arguments(self, parser):
        parser.add_argument('--models-dir', default='/models', help='Répertoire des modèles')
        parser.add_argument('--force', action='store_true', help='Forcer le re-téléchargement')

    def handle(self, *args, **options):
        models_dir = Path(options['models_dir'])
        models_dir.mkdir(exist_ok=True)

        # Modèles à télécharger
        models = {
            'distilbert-base-multilingual-cased': 'sentence-transformers/distilbert-base-multilingual-cased',
            'llama3-8b-instruct': 'meta-llama/Meta-Llama-3.1-8B-Instruct-GGUF',
            'doctr-text-detection': 'mindee/doctr-torch',
        }

        for model_name, model_path in models.items():
            self.download_model(model_name, model_path, models_dir, options['force'])

    def download_model(self, name, path, dest_dir, force=False):
        model_dir = dest_dir / name

        if model_dir.exists() and not force:
            self.stdout.write(f"Modèle {name} déjà présent")
            return

        self.stdout.write(f"Téléchargement {name}...")

        # Logic de téléchargement selon le type de modèle
        if 'sentence-transformers' in path:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(path)
            model.save(str(model_dir))
        elif 'llama' in path.lower():
            self.download_llama_model(path, model_dir)
        else:
            self.download_huggingface_model(path, model_dir)

        self.stdout.write(self.style.SUCCESS(f"Modèle {name} téléchargé"))
```

### Phase 2 : Migration de la base de données (Semaines 3-4)

#### 2.1 Création des nouvelles tables

```python
# Migration progressive par chunks
# documents/migrations/1060_ai_infrastructure.py

from django.db import migrations, models, transaction
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('documents', '1059_last_existing_migration'),
    ]

    operations = [
        # Configuration IA
        migrations.CreateModel(
            name='AIConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, unique=True, default='default')),
                ('embedding_model', models.CharField(max_length=256, default='distilbert-base-multilingual-cased')),
                ('embedding_dimension', models.PositiveIntegerField(default=768)),
                ('llm_model_path', models.CharField(max_length=512, null=True, blank=True)),
                ('search_similarity_threshold', models.DecimalField(max_digits=3, decimal_places=2, default=0.70)),
                ('enabled_features', models.JSONField(default=list)),
                ('is_active', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'AI Configuration',
                'verbose_name_plural': 'AI Configurations',
            },
        ),

        # Embeddings de documents
        migrations.CreateModel(
            name='DocumentEmbedding',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True)),
                ('document', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='documents.Document'
                )),
                ('embedding_vector', models.JSONField()),
                ('embedding_dimension', models.PositiveIntegerField()),
                ('model_name', models.CharField(max_length=256)),
                ('model_version', models.CharField(max_length=64)),
                ('confidence_score', models.DecimalField(max_digits=5, decimal_places=4, null=True)),
                ('processing_time', models.DecimalField(max_digits=8, decimal_places=3, null=True)),
                ('document_content_hash', models.CharField(max_length=64)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
        ),

        # Index pour performance
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_embedding_model "
            "ON documents_documentembedding(model_name, model_version);",
            reverse_sql="DROP INDEX IF EXISTS idx_document_embedding_model;"
        ),

        # Configuration par défaut
        migrations.RunPython(
            code=lambda apps, schema_editor: create_default_ai_config(apps),
            reverse_code=migrations.RunPython.noop,
        ),
    ]

def create_default_ai_config(apps):
    AIConfiguration = apps.get_model('documents', 'AIConfiguration')
    AIConfiguration.objects.get_or_create(
        name='default',
        defaults={
            'embedding_model': 'distilbert-base-multilingual-cased',
            'embedding_dimension': 768,
            'search_similarity_threshold': 0.70,
            'enabled_features': ['semantic_search'],
            'is_active': False,  # Sera activé manuellement
        }
    )
```

#### 2.2 Extension des modèles existants

```python
# documents/migrations/1061_extend_document.py

class Migration(migrations.Migration):
    dependencies = [
        ('documents', '1060_ai_infrastructure'),
    ]

    operations = [
        # Ajout progressif des colonnes IA au modèle Document
        migrations.AddField(
            model_name='document',
            name='ai_processing_status',
            field=models.CharField(
                max_length=32,
                choices=[
                    ('pending', 'En attente'),
                    ('processing', 'En cours'),
                    ('completed', 'Terminé'),
                    ('failed', 'Échec'),
                    ('skipped', 'Ignoré'),
                ],
                default='pending'
            ),
        ),

        migrations.AddField(
            model_name='document',
            name='ai_confidence_score',
            field=models.DecimalField(
                max_digits=5,
                decimal_places=4,
                null=True,
                blank=True,
                help_text="Score de confiance global de l'analyse IA"
            ),
        ),

        migrations.AddField(
            model_name='document',
            name='semantic_summary',
            field=models.TextField(
                blank=True,
                help_text="Résumé sémantique généré par IA"
            ),
        ),

        migrations.AddField(
            model_name='document',
            name='extracted_entities',
            field=models.JSONField(
                default=dict,
                help_text="Entités extraites par analyse IA"
            ),
        ),

        migrations.AddField(
            model_name='document',
            name='ai_last_processed',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="Dernière analyse IA"
            ),
        ),

        # Index pour requêtes fréquentes
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_ai_status "
            "ON documents_document(ai_processing_status, ai_confidence_score DESC) "
            "WHERE ai_processing_status = 'completed';",
        ),

        # Initialisation des nouvelles colonnes en batch
        migrations.RunPython(
            code=initialize_ai_fields,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

def initialize_ai_fields(apps, schema_editor):
    Document = apps.get_model('documents', 'Document')

    # Traitement par batch pour éviter les timeouts
    batch_size = 1000
    total_docs = Document.objects.count()

    for i in range(0, total_docs, batch_size):
        docs = Document.objects.all()[i:i+batch_size]
        for doc in docs:
            doc.ai_processing_status = 'pending'
            doc.extracted_entities = {}

        Document.objects.bulk_update(
            docs,
            ['ai_processing_status', 'extracted_entities'],
            batch_size=batch_size
        )
```

#### 2.3 Tables spécialisées

```python
# paperless_ai_ocr/migrations/0001_initial.py

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('documents', '1061_extend_document'),
    ]

    operations = [
        migrations.CreateModel(
            name='OCRConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, unique=True)),
                ('primary_engine', models.CharField(max_length=64, default='tesseract')),
                ('secondary_engine', models.CharField(max_length=64, null=True, blank=True)),
                ('fusion_strategy', models.CharField(max_length=64, default='confidence')),
                ('confidence_threshold', models.DecimalField(max_digits=3, decimal_places=2, default=0.80)),
                ('preprocessing_enabled', models.BooleanField(default=True)),
                ('preprocessing_options', models.JSONField(default=dict)),
                ('supported_languages', models.JSONField(default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
        ),

        migrations.CreateModel(
            name='OCRResult',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True)),
                ('document', models.ForeignKey(
                    on_delete=models.CASCADE,
                    to='documents.Document',
                    related_name='ocr_results'
                )),
                ('engine', models.CharField(max_length=64)),
                ('engine_version', models.CharField(max_length=32, null=True)),
                ('configuration', models.ForeignKey(
                    on_delete=models.SET_NULL,
                    to='paperless_ai_ocr.OCRConfiguration',
                    null=True
                )),
                ('extracted_text', models.TextField(null=True)),
                ('text_length', models.PositiveIntegerField(null=True)),
                ('overall_confidence', models.DecimalField(max_digits=5, decimal_places=4, null=True)),
                ('bounding_boxes', models.JSONField(null=True)),
                ('detected_languages', models.JSONField(null=True)),
                ('processing_time', models.DecimalField(max_digits=8, decimal_places=3, null=True)),
                ('status', models.CharField(max_length=32, default='completed')),
                ('error_message', models.TextField(null=True, blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['document', 'engine', '-created']),
                    models.Index(fields=['overall_confidence'], condition=models.Q(status='completed')),
                ],
            },
        ),
    ]
```

### Phase 3 : Migration des données existantes (Semaines 5-6)

#### 3.1 Génération des embeddings

```python
# management/commands/generate_embeddings.py
from django.core.management.base import BaseCommand
from django.db import transaction
from documents.models import Document
from paperless_ai_engine.models import DocumentEmbedding, AIConfiguration
from sentence_transformers import SentenceTransformer
import hashlib
import json
from tqdm import tqdm

class Command(BaseCommand):
    help = 'Génère les embeddings pour les documents existants'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=32)
        parser.add_argument('--start-id', type=int, default=0)
        parser.add_argument('--end-id', type=int, default=None)
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        config = AIConfiguration.objects.filter(is_active=True).first()
        if not config:
            self.stderr.write("Aucune configuration IA active trouvée")
            return

        # Charger le modèle
        self.stdout.write(f"Chargement du modèle {config.embedding_model}...")
        model = SentenceTransformer(config.embedding_model)

        # Filtrer les documents
        queryset = Document.objects.filter(id__gte=options['start_id'])
        if options['end_id']:
            queryset = queryset.filter(id__lte=options['end_id'])

        if not options['force']:
            # Exclure les documents déjà traités
            existing_embeddings = DocumentEmbedding.objects.values_list('document_id', flat=True)
            queryset = queryset.exclude(id__in=existing_embeddings)

        total_docs = queryset.count()
        self.stdout.write(f"Traitement de {total_docs} documents...")

        # Traitement par batch
        batch_size = options['batch_size']

        with tqdm(total=total_docs, desc="Génération embeddings") as pbar:
            for i in range(0, total_docs, batch_size):
                batch_docs = list(queryset[i:i+batch_size])
                self.process_batch(batch_docs, model, config, options['dry_run'])
                pbar.update(len(batch_docs))

    def process_batch(self, documents, model, config, dry_run=False):
        embeddings_to_create = []

        # Préparer les textes
        texts = []
        for doc in documents:
            text = self.prepare_text(doc)
            texts.append(text)

        # Générer les embeddings
        if texts:
            embedding_vectors = model.encode(texts, convert_to_numpy=True)

            for doc, embedding_vector in zip(documents, embedding_vectors):
                content_hash = hashlib.md5(doc.content.encode()).hexdigest()

                embedding_data = {
                    'document': doc,
                    'embedding_vector': embedding_vector.tolist(),
                    'embedding_dimension': len(embedding_vector),
                    'model_name': config.embedding_model,
                    'model_version': model.get_sentence_embedding_dimension(),
                    'document_content_hash': content_hash,
                    'processing_time': 0.0,  # À calculer si nécessaire
                }

                if not dry_run:
                    embedding_obj = DocumentEmbedding(**embedding_data)
                    embeddings_to_create.append(embedding_obj)

            # Sauvegarde par batch
            if embeddings_to_create and not dry_run:
                with transaction.atomic():
                    DocumentEmbedding.objects.bulk_create(
                        embeddings_to_create,
                        ignore_conflicts=True
                    )

                    # Mettre à jour le statut des documents
                    doc_ids = [emb.document.id for emb in embeddings_to_create]
                    Document.objects.filter(id__in=doc_ids).update(
                        ai_processing_status='completed'
                    )

    def prepare_text(self, document):
        """Prépare le texte pour l'embedding"""
        content = document.content or ""
        title = document.title or ""

        # Combiner titre et contenu avec pondération
        if title and content:
            return f"{title}. {content[:2000]}"  # Limiter la longueur
        elif title:
            return title
        else:
            return content[:2000]
```

#### 3.2 Retraitement OCR avec pipeline hybride

```python
# management/commands/reprocess_ocr.py
from django.core.management.base import BaseCommand
from documents.models import Document
from paperless_ai_ocr.models import OCRConfiguration, OCRResult
from paperless_ai_ocr.engines import TesseractEngine, DoctrEngine, HybridEngine
from celery import group

class Command(BaseCommand):
    help = 'Retraite les documents avec le pipeline OCR hybride'

    def add_arguments(self, parser):
        parser.add_argument('--document-ids', nargs='+', type=int, help='IDs spécifiques')
        parser.add_argument('--document-type', type=int, help='Type de document')
        parser.add_argument('--batch-size', type=int, default=50)
        parser.add_argument('--async', action='store_true', help='Traitement asynchrone')
        parser.add_argument('--confidence-threshold', type=float, default=0.8)
        parser.add_argument('--engines', nargs='+', default=['tesseract', 'doctr'])

    def handle(self, *args, **options):
        # Sélection des documents
        queryset = Document.objects.all()

        if options['document_ids']:
            queryset = queryset.filter(id__in=options['document_ids'])
        elif options['document_type']:
            queryset = queryset.filter(document_type_id=options['document_type'])
        else:
            # Documents sans résultats OCR récents ou avec faible confiance
            queryset = queryset.filter(
                models.Q(ocr_results__isnull=True) |
                models.Q(ocr_results__overall_confidence__lt=options['confidence_threshold'])
            ).distinct()

        total_docs = queryset.count()
        self.stdout.write(f"Retraitement OCR pour {total_docs} documents")

        # Configuration OCR
        config = OCRConfiguration.objects.filter(is_active=True).first()
        if not config:
            self.stderr.write("Aucune configuration OCR active")
            return

        # Traitement
        if options['async']:
            self.process_async(queryset, config, options)
        else:
            self.process_sync(queryset, config, options)

    def process_async(self, queryset, config, options):
        """Traitement asynchrone avec Celery"""
        from paperless_ai_ocr.tasks import reprocess_document_ocr

        batch_size = options['batch_size']

        # Créer des groupes de tâches
        for i in range(0, queryset.count(), batch_size):
            batch = queryset[i:i+batch_size]

            job = group(
                reprocess_document_ocr.s(
                    doc.id,
                    config.id,
                    options['engines']
                ) for doc in batch
            )

            result = job.apply_async()
            self.stdout.write(f"Batch {i//batch_size + 1} envoyé: {result.id}")

    def process_sync(self, queryset, config, options):
        """Traitement synchrone"""
        engines = {
            'tesseract': TesseractEngine(),
            'doctr': DoctrEngine(),
        }

        hybrid_engine = HybridEngine(
            engines=engines,
            fusion_strategy=config.fusion_strategy,
            confidence_threshold=config.confidence_threshold
        )

        for doc in tqdm(queryset, desc="Retraitement OCR"):
            try:
                # Traitement hybride
                result = hybrid_engine.process_document(doc)

                # Sauvegarde résultats
                self.save_ocr_results(doc, result, config)

            except Exception as e:
                self.stderr.write(f"Erreur document {doc.id}: {e}")

    def save_ocr_results(self, document, results, config):
        """Sauvegarde les résultats OCR"""
        with transaction.atomic():
            # Supprimer anciens résultats si nécessaire
            OCRResult.objects.filter(document=document).delete()

            # Sauvegarder nouveaux résultats
            for engine_name, engine_result in results.items():
                OCRResult.objects.create(
                    document=document,
                    engine=engine_name,
                    configuration=config,
                    extracted_text=engine_result['text'],
                    text_length=len(engine_result['text']),
                    overall_confidence=engine_result['confidence'],
                    bounding_boxes=engine_result.get('bounding_boxes'),
                    processing_time=engine_result.get('processing_time'),
                    status='completed'
                )

            # Mettre à jour le document
            if 'fused' in results:
                document.content = results['fused']['text']
                document.ai_confidence_score = results['fused']['confidence']
                document.ai_processing_status = 'completed'
                document.save()
```

#### 3.3 Migration des tâches Celery

```python
# paperless_ai_engine/tasks.py
from celery import shared_task
from django.conf import settings
from documents.models import Document
from .models import DocumentEmbedding, AIConfiguration

@shared_task(bind=True, max_retries=3)
def generate_document_embedding(self, document_id, config_id=None):
    """Génère l'embedding pour un document"""
    try:
        document = Document.objects.get(id=document_id)
        config = AIConfiguration.objects.get(
            id=config_id or AIConfiguration.objects.filter(is_active=True).first().id
        )

        # Import dynamique pour éviter les problèmes de chargement
        from sentence_transformers import SentenceTransformer
        import hashlib

        model = SentenceTransformer(config.embedding_model)

        # Préparer le texte
        text = f"{document.title or ''}. {document.content or ''}"[:2000]

        # Générer l'embedding
        embedding_vector = model.encode([text])[0]
        content_hash = hashlib.md5(document.content.encode()).hexdigest()

        # Sauvegarder
        embedding, created = DocumentEmbedding.objects.update_or_create(
            document=document,
            defaults={
                'embedding_vector': embedding_vector.tolist(),
                'embedding_dimension': len(embedding_vector),
                'model_name': config.embedding_model,
                'model_version': str(model.get_sentence_embedding_dimension()),
                'document_content_hash': content_hash,
            }
        )

        # Mettre à jour le statut du document
        document.ai_processing_status = 'completed'
        document.save()

        return f"Embedding généré pour document {document_id}"

    except Exception as exc:
        # Retry avec backoff exponentiel
        countdown = 2 ** self.request.retries
        raise self.retry(exc=exc, countdown=countdown)

@shared_task(bind=True)
def batch_generate_embeddings(self, document_ids, config_id=None):
    """Génère les embeddings pour un batch de documents"""
    from celery import group

    # Créer un groupe de tâches
    job = group(
        generate_document_embedding.s(doc_id, config_id)
        for doc_id in document_ids
    )

    result = job.apply_async()
    return f"Batch de {len(document_ids)} embeddings lancé: {result.id}"

@shared_task(bind=True, time_limit=300)
def cleanup_old_embeddings(self):
    """Nettoie les anciens embeddings obsolètes"""
    from datetime import timedelta
    from django.utils import timezone

    cutoff_date = timezone.now() - timedelta(days=90)

    # Supprimer les embeddings obsolètes
    obsolete_embeddings = DocumentEmbedding.objects.filter(
        updated__lt=cutoff_date,
        model_version__icontains='outdated'
    )

    count = obsolete_embeddings.count()
    obsolete_embeddings.delete()

    return f"Supprimé {count} embeddings obsolètes"
```

### Phase 4 : Tests et validation (Semaines 7-8)

#### 4.1 Tests d'intégrité des données

```python
# management/commands/validate_migration.py
from django.core.management.base import BaseCommand
from django.db import connection
from documents.models import Document
from paperless_ai_engine.models import DocumentEmbedding

class Command(BaseCommand):
    help = 'Valide l\'intégrité de la migration'

    def handle(self, *args, **options):
        self.stdout.write("=== Validation Migration Paperless-ngx IA ===")

        errors = []
        warnings = []

        # 1. Vérification des contraintes de base de données
        self.check_database_constraints(errors, warnings)

        # 2. Vérification de l'intégrité des embeddings
        self.check_embeddings_integrity(errors, warnings)

        # 3. Vérification des configurations
        self.check_configurations(errors, warnings)

        # 4. Tests de performance
        self.check_performance(errors, warnings)

        # Rapport final
        self.print_report(errors, warnings)

    def check_database_constraints(self, errors, warnings):
        """Vérifie les contraintes de base de données"""
        with connection.cursor() as cursor:
            # Vérifier les index
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename LIKE 'paperless_ai_%'
                OR tablename LIKE '%embedding%'
            """)
            indexes = [row[0] for row in cursor.fetchall()]

            expected_indexes = [
                'idx_document_embedding_model_version',
                'idx_document_ai_status_score',
            ]

            for idx in expected_indexes:
                if idx not in indexes:
                    errors.append(f"Index manquant: {idx}")

            # Vérifier l'intégrité référentielle
            cursor.execute("""
                SELECT COUNT(*) FROM paperless_ai_engine_documentembedding e
                LEFT JOIN documents_document d ON e.document_id = d.id
                WHERE d.id IS NULL
            """)

            orphaned_embeddings = cursor.fetchone()[0]
            if orphaned_embeddings > 0:
                errors.append(f"{orphaned_embeddings} embeddings orphelins trouvés")

    def check_embeddings_integrity(self, errors, warnings):
        """Vérifie l'intégrité des embeddings"""
        total_docs = Document.objects.count()
        embedded_docs = DocumentEmbedding.objects.count()

        coverage = (embedded_docs / total_docs) * 100 if total_docs > 0 else 0

        if coverage < 95:
            warnings.append(f"Couverture embeddings: {coverage:.1f}% (< 95%)")

        # Vérifier la dimension des vecteurs
        invalid_dimensions = DocumentEmbedding.objects.exclude(
            embedding_dimension__gt=0
        ).count()

        if invalid_dimensions > 0:
            errors.append(f"{invalid_dimensions} embeddings avec dimension invalide")

        # Vérifier la cohérence des hash
        mismatched_hashes = 0
        for embedding in DocumentEmbedding.objects.select_related('document')[:100]:
            import hashlib
            expected_hash = hashlib.md5(embedding.document.content.encode()).hexdigest()
            if embedding.document_content_hash != expected_hash:
                mismatched_hashes += 1

        if mismatched_hashes > 0:
            warnings.append(f"{mismatched_hashes} hash de contenu obsolètes détectés")

    def check_configurations(self, errors, warnings):
        """Vérifie les configurations"""
        from paperless_ai_engine.models import AIConfiguration

        active_configs = AIConfiguration.objects.filter(is_active=True).count()

        if active_configs == 0:
            errors.append("Aucune configuration IA active")
        elif active_configs > 1:
            warnings.append("Plusieurs configurations IA actives")

    def check_performance(self, errors, warnings):
        """Tests de performance basiques"""
        import time

        # Test recherche simple
        start_time = time.time()
        results = DocumentEmbedding.objects.all()[:10]
        list(results)  # Force l'évaluation
        query_time = time.time() - start_time

        if query_time > 1.0:
            warnings.append(f"Requête embeddings lente: {query_time:.2f}s")

    def print_report(self, errors, warnings):
        """Affiche le rapport de validation"""
        if errors:
            self.stdout.write(self.style.ERROR("ERREURS TROUVÉES:"))
            for error in errors:
                self.stdout.write(f"  ❌ {error}")

        if warnings:
            self.stdout.write(self.style.WARNING("AVERTISSEMENTS:"))
            for warning in warnings:
                self.stdout.write(f"  ⚠️  {warning}")

        if not errors and not warnings:
            self.stdout.write(self.style.SUCCESS("✅ Migration validée avec succès"))
        elif not errors:
            self.stdout.write(self.style.SUCCESS("✅ Migration réussie avec avertissements"))
        else:
            self.stdout.write(self.style.ERROR("❌ Migration incomplète - action requise"))
```

#### 4.2 Tests de performance

```python
# tests/test_migration_performance.py
import pytest
import time
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings
from documents.models import Document
from paperless_ai_engine.models import DocumentEmbedding

class MigrationPerformanceTest(TransactionTestCase):
    """Tests de performance post-migration"""

    def setUp(self):
        # Créer des documents de test
        self.test_documents = []
        for i in range(100):
            doc = Document.objects.create(
                title=f"Test Document {i}",
                content=f"Contenu de test pour le document {i} " * 50,
            )
            self.test_documents.append(doc)

    def test_embedding_generation_performance(self):
        """Test la performance de génération d'embeddings"""
        from paperless_ai_engine.tasks import generate_document_embedding

        start_time = time.time()

        # Générer embeddings pour 10 documents
        for doc in self.test_documents[:10]:
            generate_document_embedding(doc.id)

        elapsed_time = time.time() - start_time
        avg_time_per_doc = elapsed_time / 10

        # Assertion: moins de 2 secondes par document
        self.assertLess(avg_time_per_doc, 2.0,
                       f"Génération embedding trop lente: {avg_time_per_doc:.2f}s/doc")

    def test_search_performance(self):
        """Test la performance de recherche"""
        # Créer quelques embeddings
        for doc in self.test_documents[:20]:
            DocumentEmbedding.objects.create(
                document=doc,
                embedding_vector=[0.1] * 768,  # Vecteur fictif
                embedding_dimension=768,
                model_name='test-model',
                model_version='1.0',
                document_content_hash='test-hash'
            )

        start_time = time.time()

        # Simuler une recherche
        results = list(DocumentEmbedding.objects.select_related('document')[:10])

        elapsed_time = time.time() - start_time

        # Assertion: moins de 100ms pour une recherche simple
        self.assertLess(elapsed_time, 0.1,
                       f"Recherche trop lente: {elapsed_time:.3f}s")

    def test_database_scalability(self):
        """Test la scalabilité de la base de données"""
        # Créer beaucoup d'embeddings
        embeddings = []
        for doc in self.test_documents:
            embeddings.append(DocumentEmbedding(
                document=doc,
                embedding_vector=[0.1] * 768,
                embedding_dimension=768,
                model_name='test-model',
                model_version='1.0',
                document_content_hash=f'hash-{doc.id}'
            ))

        start_time = time.time()
        DocumentEmbedding.objects.bulk_create(embeddings)
        creation_time = time.time() - start_time

        # Assertion: création en bulk efficace
        self.assertLess(creation_time, 5.0,
                       f"Création bulk trop lente: {creation_time:.2f}s")

@pytest.mark.django_db
class APIPerformanceTest:
    """Tests de performance des nouvelles APIs"""

    def test_semantic_search_api_performance(self, client, django_user_model):
        """Test performance de l'API de recherche sémantique"""
        # Créer utilisateur et se connecter
        user = django_user_model.objects.create_user('testuser', 'test@test.com', 'pass')
        client.force_login(user)

        # Données de test
        search_data = {
            "query": "facture électricité",
            "limit": 10,
            "similarity_threshold": 0.7
        }

        start_time = time.time()
        response = client.post('/api/semantic_search/', data=search_data, content_type='application/json')
        elapsed_time = time.time() - start_time

        assert response.status_code == 200
        assert elapsed_time < 1.0, f"API recherche trop lente: {elapsed_time:.2f}s"

    def test_ai_analysis_api_performance(self, client, django_user_model):
        """Test performance de l'API d'analyse IA"""
        user = django_user_model.objects.create_user('testuser', 'test@test.com', 'pass')
        client.force_login(user)

        # Créer un document de test
        doc = Document.objects.create(
            title="Test Document",
            content="Contenu de test" * 100
        )

        analysis_data = {
            "analysis_types": ["classification"],
            "save_results": True
        }

        start_time = time.time()
        response = client.post(f'/api/documents/{doc.id}/ai_analyze/',
                              data=analysis_data, content_type='application/json')
        elapsed_time = time.time() - start_time

        assert response.status_code in [200, 202]  # 202 pour tâche async
        assert elapsed_time < 0.5, f"API analyse trop lente: {elapsed_time:.2f}s"
```

### Phase 5 : Déploiement et monitoring (Semaines 9-10)

#### 5.1 Configuration de production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  paperless:
    image: paperless-ngx:ai-extended
    environment:
      # Configuration IA
      PAPERLESS_AI_ENABLED: "true"
      PAPERLESS_AI_EMBEDDING_MODEL: "distilbert-base-multilingual-cased"
      PAPERLESS_AI_LLM_PATH: "/models/llama3-8b-instruct"
      PAPERLESS_AI_MAX_MEMORY: "4096"
      PAPERLESS_AI_GPU: "false"

      # Configuration OCR hybride
      PAPERLESS_OCR_HYBRID_ENABLED: "true"
      PAPERLESS_OCR_PRIMARY_ENGINE: "tesseract"
      PAPERLESS_OCR_SECONDARY_ENGINE: "doctr"
      PAPERLESS_OCR_FUSION_STRATEGY: "confidence"

      # Configuration calendrier
      PAPERLESS_CALENDAR_EXTRACTION: "true"
      PAPERLESS_CALENDAR_AUTO_EXPORT: "false"

      # Ressources
      PAPERLESS_TASK_WORKERS: "4"
      PAPERLESS_WORKER_TIMEOUT: "1800"

    volumes:
      - ./data:/usr/src/paperless/data
      - ./media:/usr/src/paperless/media
      - ./models:/models

    depends_on:
      - db
      - redis
      - vector-db

  vector-db:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - ./vector_data:/chroma/chroma
    environment:
      CHROMA_SERVER_AUTH_PROVIDER: "token"
      CHROMA_SERVER_AUTH_TOKEN: "${CHROMA_AUTH_TOKEN}"

  ai-worker:
    image: paperless-ngx:ai-extended
    command: celery -A paperless worker -Q ai_processing -l INFO
    environment:
      # Même config que paperless mais spécialisé pour l'IA
      PAPERLESS_AI_ENABLED: "true"
      PAPERLESS_AI_WORKER_ONLY: "true"
    volumes:
      - ./data:/usr/src/paperless/data
      - ./models:/models
    depends_on:
      - redis
      - vector-db
```

#### 5.2 Scripts de monitoring

```bash
#!/bin/bash
# scripts/monitor_ai_migration.sh

echo "=== Monitoring Migration IA Paperless-ngx ==="

# Statut des embeddings
echo "📊 Statut des embeddings:"
python manage.py shell -c "
from documents.models import Document
from paperless_ai_engine.models import DocumentEmbedding

total_docs = Document.objects.count()
embedded_docs = DocumentEmbedding.objects.count()
pending_docs = Document.objects.filter(ai_processing_status='pending').count()

print(f'Total documents: {total_docs}')
print(f'Documents avec embeddings: {embedded_docs}')
print(f'Documents en attente: {pending_docs}')
print(f'Couverture: {(embedded_docs/total_docs*100):.1f}%')
"

# Performance des tâches Celery
echo "🔄 Performance Celery:"
celery -A paperless inspect stats | jq '.["celery@worker"]["pool"]["max-concurrency"]'

# Utilisation mémoire
echo "💾 Utilisation mémoire:"
free -h

# Espace disque
echo "💿 Espace disque:"
df -h | grep -E "(models|vector_data|media)"

# Statut des services IA
echo "🤖 Services IA:"
curl -s http://localhost:8000/api/v1/heartbeat | jq '.status' || echo "Vector DB non disponible"

# Métriques de performance récentes
echo "📈 Métriques récentes (24h):"
python manage.py shell -c "
from django.utils import timezone
from datetime import timedelta
from paperless_ai_engine.models import SemanticQuery
from documents.models import PaperlessTask

yesterday = timezone.now() - timedelta(days=1)

# Requêtes sémantiques
semantic_queries = SemanticQuery.objects.filter(created__gte=yesterday)
avg_search_time = semantic_queries.aggregate(avg_time=models.Avg('total_time'))['avg_time']

# Tâches IA
ai_tasks = PaperlessTask.objects.filter(
    task_name__in=['ai_analyze', 'generate_embedding'],
    date_created__gte=yesterday
)

print(f'Requêtes sémantiques: {semantic_queries.count()}')
print(f'Temps moyen recherche: {avg_search_time:.3f}s' if avg_search_time else 'N/A')
print(f'Tâches IA: {ai_tasks.count()}')
print(f'Tâches réussies: {ai_tasks.filter(status=\"SUCCESS\").count()}')
"
```

#### 5.3 Alertes et notifications

```python
# monitoring/alerts.py
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = 'Vérifie l\'état du système IA et envoie des alertes'

    def handle(self, *args, **options):
        alerts = []

        # Vérifier la couverture des embeddings
        coverage = self.check_embedding_coverage()
        if coverage < 95:
            alerts.append(f"⚠️ Couverture embeddings faible: {coverage:.1f}%")

        # Vérifier les erreurs récentes
        error_count = self.check_recent_errors()
        if error_count > 10:
            alerts.append(f"❌ {error_count} erreurs IA dans les dernières 24h")

        # Vérifier la performance
        avg_time = self.check_performance()
        if avg_time > 5.0:
            alerts.append(f"🐌 Performance dégradée: {avg_time:.2f}s moyenne")

        # Vérifier l'espace disque
        disk_usage = self.check_disk_space()
        if disk_usage > 90:
            alerts.append(f"💿 Espace disque critique: {disk_usage}%")

        # Envoyer alertes si nécessaire
        if alerts:
            self.send_alerts(alerts)
        else:
            self.stdout.write("✅ Tous les systèmes fonctionnent normalement")

    def check_embedding_coverage(self):
        from documents.models import Document
        from paperless_ai_engine.models import DocumentEmbedding

        total = Document.objects.count()
        embedded = DocumentEmbedding.objects.count()
        return (embedded / total) * 100 if total > 0 else 0

    def check_recent_errors(self):
        from documents.models import PaperlessTask

        yesterday = timezone.now() - timedelta(days=1)
        return PaperlessTask.objects.filter(
            task_name__icontains='ai',
            status='FAILURE',
            date_created__gte=yesterday
        ).count()

    def check_performance(self):
        from paperless_ai_engine.models import SemanticQuery

        yesterday = timezone.now() - timedelta(days=1)
        queries = SemanticQuery.objects.filter(created__gte=yesterday)

        if queries.exists():
            return queries.aggregate(avg_time=models.Avg('total_time'))['avg_time'] or 0
        return 0

    def check_disk_space(self):
        import shutil

        # Vérifier l'espace disque des modèles
        total, used, free = shutil.disk_usage('/models')
        return (used / total) * 100

    def send_alerts(self, alerts):
        subject = f"[Paperless-ngx] Alertes système IA - {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        message = "\n".join(alerts)

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_EMAIL],
            fail_silently=False,
        )

        self.stdout.write(f"📧 {len(alerts)} alertes envoyées")
```

## Rollback et récupération

### Plan de rollback complet

```bash
#!/bin/bash
# scripts/rollback_migration.sh

set -e

echo "⚠️  ROLLBACK MIGRATION IA PAPERLESS-NGX ⚠️"
echo "Cette opération va annuler la migration IA"
read -p "Êtes-vous sûr? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Rollback annulé"
    exit 1
fi

BACKUP_DIR="/backup/paperless_migration_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "1. Sauvegarde de l'état actuel..."
python manage.py document_exporter --data-only "$BACKUP_DIR/pre_rollback_export.zip"

echo "2. Désactivation des fonctionnalités IA..."
python manage.py shell -c "
from paperless_ai_engine.models import AIConfiguration
AIConfiguration.objects.all().update(is_active=False)
"

echo "3. Arrêt des tâches Celery IA..."
celery -A paperless purge -Q ai_processing
celery -A paperless control shutdown

echo "4. Rollback des migrations..."
python manage.py migrate paperless_ai_engine zero
python manage.py migrate paperless_ai_ocr zero
python manage.py migrate paperless_calendar zero
python manage.py migrate documents 1059  # Dernière migration avant IA

echo "5. Suppression des nouvelles colonnes..."
python manage.py shell -c "
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('ALTER TABLE documents_document DROP COLUMN IF EXISTS ai_processing_status')
    cursor.execute('ALTER TABLE documents_document DROP COLUMN IF EXISTS ai_confidence_score')
    cursor.execute('ALTER TABLE documents_document DROP COLUMN IF EXISTS semantic_summary')
    cursor.execute('ALTER TABLE documents_document DROP COLUMN IF EXISTS extracted_entities')
    cursor.execute('ALTER TABLE documents_document DROP COLUMN IF EXISTS ai_last_processed')
"

echo "6. Nettoyage des fichiers..."
rm -rf /models/ai_models/
rm -rf /data/vector_index/

echo "7. Restauration de la configuration..."
# Restaurer docker-compose.yml original si sauvegardé
if [ -f "$BACKUP_DIR/docker-compose.yml.bak" ]; then
    cp "$BACKUP_DIR/docker-compose.yml.bak" docker-compose.yml
fi

echo "8. Redémarrage des services..."
docker-compose restart paperless redis db

echo "✅ Rollback terminé"
echo "📝 Vérifiez les logs et testez les fonctionnalités de base"
```

### Vérification post-rollback

```python
# management/commands/verify_rollback.py
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Vérifie que le rollback a été effectué correctement'

    def handle(self, *args, **options):
        issues = []

        # Vérifier que les tables IA n'existent plus
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_name LIKE 'paperless_ai_%'
            """)
            ai_tables = cursor.fetchall()

            if ai_tables:
                issues.append(f"Tables IA encore présentes: {ai_tables}")

            # Vérifier que les colonnes IA ont été supprimées
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'documents_document'
                AND column_name LIKE 'ai_%'
            """)
            ai_columns = cursor.fetchall()

            if ai_columns:
                issues.append(f"Colonnes IA encore présentes: {ai_columns}")

        # Vérifier les fonctionnalités de base
        from documents.models import Document
        doc_count = Document.objects.count()
        self.stdout.write(f"Documents accessibles: {doc_count}")

        if issues:
            self.stderr.write("❌ Problèmes détectés:")
            for issue in issues:
                self.stderr.write(f"  - {issue}")
        else:
            self.stdout.write("✅ Rollback vérifié avec succès")
```

## Timeline et jalons

### Planning détaillé

| Semaine | Phase             | Activités principales                                                            | Livrables                                    |
| ------- | ----------------- | -------------------------------------------------------------------------------- | -------------------------------------------- |
| 1-2     | Préparation       | - Audit infrastructure<br>- Installation dépendances<br>- Téléchargement modèles | - Rapport d'audit<br>- Environnement de test |
| 3-4     | Migration DB      | - Nouvelles tables<br>- Extension modèles<br>- Tests d'intégrité                 | - Schéma migré<br>- Tests validés            |
| 5-6     | Migration données | - Génération embeddings<br>- Retraitement OCR<br>- Configuration Celery          | - Données migrées<br>- Performance optimisée |
| 7-8     | Tests             | - Tests fonctionnels<br>- Tests performance<br>- Tests charge                    | - Suite de tests<br>- Rapport validation     |
| 9-10    | Déploiement       | - Mise en production<br>- Monitoring<br>- Formation                              | - Système déployé<br>- Documentation         |

### Critères de succès

#### Phase 1 - Préparation
- ✅ Sauvegarde complète validée
- ✅ Dépendances IA installées sans conflit
- ✅ Modèles téléchargés et fonctionnels
- ✅ Environnement de test opérationnel

#### Phase 2 - Migration Base de Données
- ✅ Toutes les migrations appliquées sans erreur
- ✅ Contraintes d'intégrité respectées
- ✅ Index de performance créés
- ✅ Tests d'intégrité passés

#### Phase 3 - Migration Données
- ✅ >95% des documents ont des embeddings
- ✅ Retraitement OCR sans perte de données
- ✅ Tâches Celery fonctionnelles
- ✅ Performance acceptable (<2s/document)

#### Phase 4 - Tests
- ✅ Tous les tests unitaires passent
- ✅ Tests d'intégration réussis
- ✅ Performance conforme aux exigences
- ✅ Pas de régression fonctionnelle

#### Phase 5 - Déploiement
- ✅ Déploiement sans interruption
- ✅ Monitoring opérationnel
- ✅ Alertes configurées
- ✅ Documentation complète

### Points de contrôle

**Checkpoint 1 (Fin semaine 2)** : Go/No-Go pour migration DB
- Vérification infrastructure
- Validation des prérequis
- Approbation équipe

**Checkpoint 2 (Fin semaine 4)** : Go/No-Go pour migration données
- Intégrité schéma validée
- Performance DB acceptable
- Tests d'intégrité OK

**Checkpoint 3 (Fin semaine 6)** : Go/No-Go pour tests
- Données migrées avec succès
- Fonctionnalités IA opérationnelles
- Performance conforme

**Checkpoint 4 (Fin semaine 8)** : Go/No-Go pour production
- Tous les tests passés
- Validation utilisateur
- Plan de rollback testé

**Checkpoint Final (Fin semaine 10)** : Clôture migration
- Système stable en production
- Monitoring fonctionnel
- Formation équipe terminée

Ce plan de migration garantit une transition en douceur vers l'architecture IA étendue tout en préservant la fiabilité et les performances du système Paperless-ngx existant.
