"""
Commande pour initialiser le système de classification intelligente

Cette commande configure les modèles IA par défaut, génère les embeddings
pour les documents existants et lance les premières classifications.
"""

import os
import logging
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone

from documents.models import Document, DocumentType, Correspondent, Tag
from paperless_ai.models import AIModel
from paperless_ai.classification import HybridClassificationEngine
from paperless_ai.tasks import (
    batch_generate_embeddings, batch_classify_documents
)

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Commande d'initialisation du système IA"""

    help = 'Initialise le système de classification intelligente avec les modèles par défaut'

    def add_arguments(self, parser):
        """Ajoute les arguments de la commande"""
        parser.add_argument(
            '--create-default-models',
            action='store_true',
            help='Crée les modèles IA par défaut'
        )

        parser.add_argument(
            '--generate-embeddings',
            action='store_true',
            help='Génère les embeddings pour les documents existants'
        )

        parser.add_argument(
            '--classify-documents',
            action='store_true',
            help='Lance la classification automatique des documents'
        )

        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Taille des lots pour le traitement (défaut: 50)'
        )

        parser.add_argument(
            '--owner',
            type=str,
            help='Nom d\'utilisateur propriétaire des modèles (défaut: premier superuser)'
        )

        parser.add_argument(
            '--force',
            action='store_true',
            help='Force la régénération même si les données existent'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans l\'exécuter'
        )

    def handle(self, *args, **options):
        """Exécute la commande"""
        self.verbosity = options['verbosity']
        self.dry_run = options['dry_run']
        self.force = options['force']
        self.batch_size = options['batch_size']

        # Obtenir le propriétaire des modèles
        owner = self._get_owner(options.get('owner'))
        if not owner:
            raise CommandError("Impossible de trouver un propriétaire pour les modèles")

        self.stdout.write(
            self.style.SUCCESS(f"Initialisation du système IA (propriétaire: {owner.username})")
        )

        # Vérifier les dépendances
        if not self._check_dependencies():
            raise CommandError("Dépendances manquantes. Installez les packages ML requis.")

        # Exécuter les étapes demandées
        if options['create_default_models']:
            self._create_default_models(owner)

        if options['generate_embeddings']:
            self._generate_embeddings()

        if options['classify_documents']:
            self._classify_documents()

        if not any([
            options['create_default_models'],
            options['generate_embeddings'],
            options['classify_documents']
        ]):
            # Par défaut, tout faire
            self._create_default_models(owner)
            self._generate_embeddings()
            self._classify_documents()

        self.stdout.write(
            self.style.SUCCESS("Initialisation du système IA terminée !")
        )

    def _get_owner(self, username: Optional[str]) -> Optional[User]:
        """Obtient l'utilisateur propriétaire des modèles"""
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"Utilisateur '{username}' non trouvé")
                )

        # Chercher le premier superuser
        superuser = User.objects.filter(is_superuser=True).first()
        if superuser:
            return superuser

        # Chercher le premier utilisateur actif
        return User.objects.filter(is_active=True).first()

    def _check_dependencies(self) -> bool:
        """Vérifie que les dépendances ML sont disponibles"""
        try:
            import torch
            import transformers
            from sklearn.metrics.pairwise import cosine_similarity

            if self.verbosity >= 2:
                self.stdout.write("✓ PyTorch disponible")
                self.stdout.write("✓ Transformers disponible")
                self.stdout.write("✓ Scikit-learn disponible")

            # Stocker la référence à torch pour utilisation ultérieure
            self.torch_available = True
            self.torch = torch

            return True

        except ImportError as e:
            self.stdout.write(
                self.style.ERROR(f"Dépendance manquante: {e}")
            )
            self.torch_available = False
            return False

    def _create_default_models(self, owner: User):
        """Crée les modèles IA par défaut"""
        self.stdout.write("Création des modèles IA par défaut...")

        # Configuration des modèles par défaut
        default_models = [
            {
                'name': 'DistilBERT Classification Française',
                'model_type': 'classification',
                'language': 'fr',
                'model_path': 'distilbert-base-multilingual-cased',
                'config': {
                    'model_name': 'distilbert-base-multilingual-cased',
                    'max_length': 512,
                    'num_labels': None,  # Sera calculé automatiquement
                    'use_cuda': self.torch.cuda.is_available() if hasattr(self, 'torch') else False,
                    'learning_rate': 2e-5,
                    'batch_size': 16,
                    'num_epochs': 3,
                    'warmup_steps': 500,
                    'weight_decay': 0.01
                }
            },
            {
                'name': 'DistilBERT Classification Anglaise',
                'model_type': 'classification',
                'language': 'en',
                'model_path': 'distilbert-base-multilingual-cased',
                'config': {
                    'model_name': 'distilbert-base-multilingual-cased',
                    'max_length': 512,
                    'num_labels': None,
                    'use_cuda': self.torch.cuda.is_available() if hasattr(self, 'torch') else False,
                    'learning_rate': 2e-5,
                    'batch_size': 16,
                    'num_epochs': 3,
                    'warmup_steps': 500,
                    'weight_decay': 0.01
                }
            },
            {
                'name': 'Moteur de Recherche Sémantique',
                'model_type': 'search',
                'language': 'multilingual',
                'model_path': 'distilbert-base-multilingual-cased',
                'config': {
                    'model_name': 'distilbert-base-multilingual-cased',
                    'max_length': 512,
                    'pooling_strategy': 'mean',
                    'use_cuda': self.torch.cuda.is_available() if hasattr(self, 'torch') else False
                }
            }
        ]

        created_count = 0

        for model_config in default_models:
            # Vérifier si le modèle existe déjà
            existing = AIModel.objects.filter(
                name=model_config['name'],
                owner=owner
            ).first()

            if existing and not self.force:
                if self.verbosity >= 2:
                    self.stdout.write(f"  - Modèle '{model_config['name']}' existe déjà")
                continue

            if self.dry_run:
                self.stdout.write(f"  - Créerait le modèle '{model_config['name']}'")
                continue

            # Créer ou mettre à jour le modèle
            if existing:
                for key, value in model_config.items():
                    if key != 'name':  # Ne pas changer le nom
                        setattr(existing, key, value)
                existing.save()
                self.stdout.write(f"  ✓ Modèle '{model_config['name']}' mis à jour")
            else:
                AIModel.objects.create(owner=owner, **model_config)
                self.stdout.write(f"  ✓ Modèle '{model_config['name']}' créé")

            created_count += 1

        if created_count == 0 and not self.dry_run:
            self.stdout.write("  Aucun nouveau modèle créé")
        elif self.dry_run:
            self.stdout.write(f"  {len(default_models)} modèle(s) serai(en)t créé(s)")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"  {created_count} modèle(s) créé(s)/mis à jour")
            )

    def _generate_embeddings(self):
        """Génère les embeddings pour les documents existants"""
        self.stdout.write("Génération des embeddings...")

        # Compter les documents
        total_docs = Document.objects.count()
        if total_docs == 0:
            self.stdout.write("  Aucun document à traiter")
            return

        # Compter les documents sans embedding
        from paperless_ai.models import DocumentEmbedding

        if self.force:
            docs_to_process = list(Document.objects.values_list('id', flat=True))
        else:
            existing_embeddings = set(
                DocumentEmbedding.objects.values_list('document_id', flat=True)
            )
            docs_to_process = list(
                Document.objects.exclude(id__in=existing_embeddings).values_list('id', flat=True)
            )

        if not docs_to_process:
            self.stdout.write("  Tous les documents ont déjà des embeddings")
            return

        self.stdout.write(f"  {len(docs_to_process)} document(s) à traiter")

        if self.dry_run:
            self.stdout.write(f"  Lancerait la génération d'embeddings par lots de {self.batch_size}")
            return

        # Traiter par lots
        for i in range(0, len(docs_to_process), self.batch_size):
            batch = docs_to_process[i:i + self.batch_size]

            if self.verbosity >= 2:
                self.stdout.write(
                    f"  Traitement du lot {i//self.batch_size + 1} "
                    f"({len(batch)} documents)"
                )

            # Lancer la tâche Celery
            task_result = batch_generate_embeddings.delay(batch, self.force)

            if self.verbosity >= 2:
                self.stdout.write(f"    Tâche lancée: {task_result.id}")

        self.stdout.write(
            self.style.SUCCESS(
                f"  Génération d'embeddings lancée pour {len(docs_to_process)} document(s)"
            )
        )

    def _classify_documents(self):
        """Lance la classification automatique des documents"""
        self.stdout.write("Classification automatique des documents...")

        # Compter les documents
        total_docs = Document.objects.count()
        if total_docs == 0:
            self.stdout.write("  Aucun document à traiter")
            return

        # Compter les documents sans classification
        from paperless_ai.models import DocumentClassification

        if self.force:
            docs_to_process = list(Document.objects.values_list('id', flat=True))
        else:
            existing_classifications = set(
                DocumentClassification.objects.values_list('document_id', flat=True)
            )
            docs_to_process = list(
                Document.objects.exclude(id__in=existing_classifications).values_list('id', flat=True)
            )

        if not docs_to_process:
            self.stdout.write("  Tous les documents ont déjà des classifications")
            return

        self.stdout.write(f"  {len(docs_to_process)} document(s) à traiter")

        if self.dry_run:
            self.stdout.write(f"  Lancerait la classification par lots de {self.batch_size}")
            return

        # Traiter par lots
        for i in range(0, len(docs_to_process), self.batch_size):
            batch = docs_to_process[i:i + self.batch_size]

            if self.verbosity >= 2:
                self.stdout.write(
                    f"  Traitement du lot {i//self.batch_size + 1} "
                    f"({len(batch)} documents)"
                )

            # Lancer la tâche Celery
            task_result = batch_classify_documents.delay(batch, self.force)

            if self.verbosity >= 2:
                self.stdout.write(f"    Tâche lancée: {task_result.id}")

        self.stdout.write(
            self.style.SUCCESS(
                f"  Classification lancée pour {len(docs_to_process)} document(s)"
            )
        )
