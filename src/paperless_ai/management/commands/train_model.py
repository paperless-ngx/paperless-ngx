"""
Commande pour entraîner les modèles de classification

Cette commande lance l'entraînement d'un modèle de classification
en utilisant les données validées existantes.
"""

import logging
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model

from paperless_ai.models import AIModel, TrainingJob
from paperless_ai.tasks import train_classification_model

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Commande d'entraînement des modèles IA"""

    help = 'Lance l\'entraînement d\'un modèle de classification'

    def add_arguments(self, parser):
        """Ajoute les arguments de la commande"""
        parser.add_argument(
            'model_id',
            type=int,
            help='ID du modèle à entraîner'
        )

        parser.add_argument(
            '--epochs',
            type=int,
            default=3,
            help='Nombre d\'époques d\'entraînement (défaut: 3)'
        )

        parser.add_argument(
            '--batch-size',
            type=int,
            default=16,
            help='Taille des lots d\'entraînement (défaut: 16)'
        )

        parser.add_argument(
            '--learning-rate',
            type=float,
            default=2e-5,
            help='Taux d\'apprentissage (défaut: 2e-5)'
        )

        parser.add_argument(
            '--test-split',
            type=float,
            default=0.2,
            help='Proportion des données pour les tests (défaut: 0.2)'
        )

        parser.add_argument(
            '--use-validated-only',
            action='store_true',
            help='Utiliser uniquement les classifications validées'
        )

        parser.add_argument(
            '--min-samples-per-class',
            type=int,
            default=5,
            help='Nombre minimum d\'échantillons par classe (défaut: 5)'
        )

        parser.add_argument(
            '--wait',
            action='store_true',
            help='Attendre la fin de l\'entraînement'
        )

        parser.add_argument(
            '--force',
            action='store_true',
            help='Forcer l\'entraînement même si un autre est en cours'
        )

    def handle(self, *args, **options):
        """Exécute la commande"""
        model_id = options['model_id']

        try:
            model = AIModel.objects.get(id=model_id)
        except AIModel.DoesNotExist:
            raise CommandError(f"Modèle avec l'ID {model_id} non trouvé")

        self.stdout.write(f"Entraînement du modèle: {model.name}")

        # Vérifier l'état du modèle
        if model.status == 'training' and not options['force']:
            raise CommandError("Le modèle est déjà en cours d'entraînement. Utilisez --force pour forcer.")

        # Vérifier qu'il y a des données d'entraînement
        from paperless_ai.models import DocumentClassification

        training_data_query = DocumentClassification.objects.filter(
            model=model
        )

        if options['use_validated_only']:
            training_data_query = training_data_query.filter(is_validated=True)

        # Compter les échantillons par classe
        data_stats = self._analyze_training_data(training_data_query, options['min_samples_per_class'])

        if not data_stats['has_sufficient_data']:
            self.stdout.write(
                self.style.WARNING("Données d'entraînement insuffisantes:")
            )
            for issue in data_stats['issues']:
                self.stdout.write(f"  - {issue}")

            if not options['force']:
                raise CommandError("Utilisez --force pour entraîner malgré les données insuffisantes")

        # Afficher les statistiques
        self.stdout.write("Statistiques des données d'entraînement:")
        self.stdout.write(f"  Total d'échantillons: {data_stats['total_samples']}")
        self.stdout.write(f"  Classes de types de documents: {data_stats['document_type_classes']}")
        self.stdout.write(f"  Classes de correspondants: {data_stats['correspondent_classes']}")
        self.stdout.write(f"  Tags uniques: {data_stats['unique_tags']}")

        # Configuration d'entraînement
        training_config = {
            'epochs': options['epochs'],
            'batch_size': options['batch_size'],
            'learning_rate': options['learning_rate'],
            'test_split': options['test_split'],
            'use_validated_only': options['use_validated_only'],
            'min_samples_per_class': options['min_samples_per_class']
        }

        dataset_info = {
            'total_samples': data_stats['total_samples'],
            'document_type_classes': data_stats['document_type_classes'],
            'correspondent_classes': data_stats['correspondent_classes'],
            'unique_tags': data_stats['unique_tags'],
            'use_validated_only': options['use_validated_only']
        }

        # Créer la tâche d'entraînement
        training_job = TrainingJob.objects.create(
            model=model,
            training_config=training_config,
            dataset_info=dataset_info,
            started_by=None  # Commande CLI
        )

        self.stdout.write(f"Tâche d'entraînement créée: {training_job.id}")

        # Lancer l'entraînement
        task_result = train_classification_model.delay(str(training_job.id))

        self.stdout.write(f"Entraînement lancé (tâche Celery: {task_result.id})")

        if options['wait']:
            self.stdout.write("Attente de la fin de l'entraînement...")

            try:
                # Attendre le résultat (timeout de 1 heure)
                result = task_result.get(timeout=3600)

                # Recharger la tâche pour voir les résultats
                training_job.refresh_from_db()

                self.stdout.write(
                    self.style.SUCCESS(f"Entraînement terminé avec succès!")
                )

                if training_job.final_accuracy:
                    self.stdout.write(f"Précision finale: {training_job.final_accuracy:.1%}")

                if training_job.training_time_seconds:
                    self.stdout.write(f"Temps d'entraînement: {training_job.training_time_seconds:.0f}s")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Erreur durant l'entraînement: {e}")
                )
                raise CommandError("L'entraînement a échoué")
        else:
            self.stdout.write(
                "Entraînement lancé en arrière-plan. "
                f"Surveillez la tâche {training_job.id} dans l'admin."
            )

    def _analyze_training_data(self, training_data_query, min_samples_per_class: int) -> dict:
        """Analyse les données d'entraînement disponibles"""
        from django.db.models import Count

        total_samples = training_data_query.count()

        # Analyser les types de documents
        doc_type_stats = training_data_query.filter(
            predicted_document_type__isnull=False
        ).values('predicted_document_type__name').annotate(
            count=Count('id')
        ).order_by('-count')

        # Analyser les correspondants
        correspondent_stats = training_data_query.filter(
            predicted_correspondent__isnull=False
        ).values('predicted_correspondent__name').annotate(
            count=Count('id')
        ).order_by('-count')

        # Analyser les tags
        tag_stats = training_data_query.filter(
            predicted_tags__isnull=False
        ).values('predicted_tags__name').annotate(
            count=Count('id')
        ).order_by('-count')

        # Vérifier les problèmes
        issues = []
        has_sufficient_data = True

        if total_samples < 10:
            issues.append(f"Trop peu d'échantillons total ({total_samples} < 10)")
            has_sufficient_data = False

        # Vérifier les classes de types de documents
        insufficient_doc_types = [
            stat for stat in doc_type_stats
            if stat['count'] < min_samples_per_class
        ]
        if insufficient_doc_types:
            issues.append(
                f"{len(insufficient_doc_types)} type(s) de document avec moins de "
                f"{min_samples_per_class} échantillons"
            )

        # Vérifier les classes de correspondants
        insufficient_correspondents = [
            stat for stat in correspondent_stats
            if stat['count'] < min_samples_per_class
        ]
        if insufficient_correspondents:
            issues.append(
                f"{len(insufficient_correspondents)} correspondant(s) avec moins de "
                f"{min_samples_per_class} échantillons"
            )

        return {
            'total_samples': total_samples,
            'document_type_classes': len(doc_type_stats),
            'correspondent_classes': len(correspondent_stats),
            'unique_tags': len(tag_stats),
            'has_sufficient_data': has_sufficient_data,
            'issues': issues,
            'doc_type_stats': list(doc_type_stats),
            'correspondent_stats': list(correspondent_stats),
            'tag_stats': list(tag_stats)
        }
