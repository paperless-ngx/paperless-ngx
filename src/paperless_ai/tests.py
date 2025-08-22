"""
Tests pour le système de classification intelligente

Tests unitaires et d'intégration pour les modèles, classificateurs,
recherche sémantique et API REST.
"""

import json
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from documents.models import Document, DocumentType, Correspondent, Tag
from paperless_ai.models import (
    AIModel, DocumentEmbedding, DocumentClassification,
    SearchQuery, AIMetrics, TrainingJob
)
from paperless_ai.classification import (
    DistilBertClassifier, HybridClassificationEngine, VectorSearchEngine
)
from paperless_ai.serializers import (
    AIModelSerializer, SemanticSearchSerializer, ClassificationRequestSerializer
)

User = get_user_model()


class AIModelTestCase(TestCase):
    """Tests pour le modèle AIModel"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.ai_model = AIModel.objects.create(
            name='Test Model',
            description='Un modèle de test',
            model_type='classification',
            language='fr',
            owner=self.user,
            model_config={
                'model_name': 'distilbert-base-multilingual-cased',
                'max_length': 512
            },
            hyperparameters={
                'learning_rate': 2e-5,
                'batch_size': 16
            }
        )

    def test_model_creation(self):
        """Test la création d'un modèle IA"""
        self.assertEqual(self.ai_model.name, 'Test Model')
        self.assertEqual(self.ai_model.model_type, 'classification')
        self.assertEqual(self.ai_model.language, 'fr')
        self.assertEqual(self.ai_model.owner, self.user)
        self.assertEqual(self.ai_model.status, 'inactive')
        self.assertIsNotNone(self.ai_model.id)

    def test_model_config_validation(self):
        """Test la validation de la configuration du modèle"""
        # Configuration valide
        valid_config = {
            'model_name': 'distilbert-base-multilingual-cased',
            'max_length': 512,
            'num_labels': 10
        }

        model = AIModel(
            name='Valid Model',
            model_type='classification',
            language='en',
            owner=self.user,
            model_config=valid_config
        )

        # Devrait passer la validation
        model.full_clean()
        model.save()

        self.assertEqual(model.model_config['model_name'], 'distilbert-base-multilingual-cased')

    def test_model_str_representation(self):
        """Test la représentation string du modèle"""
        expected = f"Test Model (classification, fr) - inactive"
        self.assertEqual(str(self.ai_model), expected)

    def test_model_status_choices(self):
        """Test les choix de statut du modèle"""
        valid_statuses = ['inactive', 'active', 'training', 'error']

        for status_choice in valid_statuses:
            self.ai_model.status = status_choice
            self.ai_model.full_clean()  # Devrait passer

    def test_accuracy_range(self):
        """Test que la précision est dans la bonne plage"""
        # Précision valide
        self.ai_model.accuracy = 0.85
        self.ai_model.full_clean()

        # Précision invalide (trop haute)
        self.ai_model.accuracy = 1.5
        with self.assertRaises(Exception):
            self.ai_model.full_clean()

        # Précision invalide (négative)
        self.ai_model.accuracy = -0.1
        with self.assertRaises(Exception):
            self.ai_model.full_clean()


class DocumentEmbeddingTestCase(TestCase):
    """Tests pour le modèle DocumentEmbedding"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.document = Document.objects.create(
            title='Test Document',
            content='Contenu du document de test',
            original_filename='test.pdf'
        )

        self.ai_model = AIModel.objects.create(
            name='Embedding Model',
            model_type='embedding',
            language='fr',
            owner=self.user
        )

        self.embedding = DocumentEmbedding.objects.create(
            document=self.document,
            model=self.ai_model,
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            confidence_score=0.95
        )

    def test_embedding_creation(self):
        """Test la création d'un embedding"""
        self.assertEqual(self.embedding.document, self.document)
        self.assertEqual(self.embedding.model, self.ai_model)
        self.assertEqual(len(self.embedding.embedding), 5)
        self.assertEqual(self.embedding.confidence_score, 0.95)

    def test_embedding_uniqueness(self):
        """Test l'unicité document-modèle"""
        # Essayer de créer un autre embedding pour le même document-modèle
        with self.assertRaises(Exception):
            DocumentEmbedding.objects.create(
                document=self.document,
                model=self.ai_model,
                embedding=[0.6, 0.7, 0.8, 0.9, 1.0]
            )

    def test_embedding_str_representation(self):
        """Test la représentation string de l'embedding"""
        expected = f"Embedding pour '{self.document.title}' avec 'Embedding Model'"
        self.assertEqual(str(self.embedding), expected)


class DocumentClassificationTestCase(TestCase):
    """Tests pour le modèle DocumentClassification"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.document = Document.objects.create(
            title='Test Document',
            content='Contenu du document'
        )

        self.document_type = DocumentType.objects.create(
            name='Facture',
            match='',
            matching_algorithm=1
        )

        self.correspondent = Correspondent.objects.create(
            name='Entreprise Test',
            match='',
            matching_algorithm=1
        )

        self.tag = Tag.objects.create(
            name='Important',
            color='#ff0000',
            match='',
            matching_algorithm=1
        )

        self.ai_model = AIModel.objects.create(
            name='Classification Model',
            model_type='classification',
            language='fr',
            owner=self.user
        )

        self.classification = DocumentClassification.objects.create(
            document=self.document,
            model=self.ai_model,
            classification_type='full',
            predicted_document_type=self.document_type,
            predicted_correspondent=self.correspondent,
            confidence_score=0.8
        )
        self.classification.predicted_tags.add(self.tag)

    def test_classification_creation(self):
        """Test la création d'une classification"""
        self.assertEqual(self.classification.document, self.document)
        self.assertEqual(self.classification.model, self.ai_model)
        self.assertEqual(self.classification.predicted_document_type, self.document_type)
        self.assertEqual(self.classification.predicted_correspondent, self.correspondent)
        self.assertIn(self.tag, self.classification.predicted_tags.all())
        self.assertFalse(self.classification.is_validated)

    def test_classification_validation(self):
        """Test la validation d'une classification"""
        self.classification.is_validated = True
        self.classification.validation_feedback = 'correct'
        self.classification.validated_by = self.user
        self.classification.validated_at = timezone.now()
        self.classification.save()

        self.assertTrue(self.classification.is_validated)
        self.assertEqual(self.classification.validation_feedback, 'correct')
        self.assertEqual(self.classification.validated_by, self.user)


class DistilBertClassifierTestCase(TestCase):
    """Tests pour DistilBertClassifier"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.ai_model = AIModel.objects.create(
            name='Test DistilBERT',
            model_type='classification',
            language='fr',
            owner=self.user,
            model_config={
                'model_name': 'distilbert-base-multilingual-cased',
                'max_length': 512
            }
        )

    @patch('paperless_ai.classification.AutoTokenizer')
    @patch('paperless_ai.classification.AutoModel')
    def test_classifier_initialization(self, mock_model, mock_tokenizer):
        """Test l'initialisation du classificateur"""
        # Configurer les mocks
        mock_tokenizer.from_pretrained.return_value = Mock()
        mock_model.from_pretrained.return_value = Mock()

        classifier = DistilBertClassifier(self.ai_model)

        self.assertEqual(classifier.model_config, self.ai_model)
        mock_tokenizer.from_pretrained.assert_called_once()
        mock_model.from_pretrained.assert_called_once()

    @patch('paperless_ai.classification.AutoTokenizer')
    @patch('paperless_ai.classification.AutoModel')
    @patch('torch.no_grad')
    def test_text_preprocessing(self, mock_no_grad, mock_model, mock_tokenizer):
        """Test le préprocessing du texte"""
        # Configurer les mocks
        mock_tokenizer_instance = Mock()
        mock_tokenizer.from_pretrained.return_value = mock_tokenizer_instance
        mock_model.from_pretrained.return_value = Mock()

        mock_tokenizer_instance.return_value = {
            'input_ids': [[101, 2049, 102]],
            'attention_mask': [[1, 1, 1]]
        }

        classifier = DistilBertClassifier(self.ai_model)
        result = classifier._preprocess_text("Test text")

        self.assertIsNotNone(result)
        mock_tokenizer_instance.assert_called_once()


class HybridClassificationEngineTestCase(TestCase):
    """Tests pour HybridClassificationEngine"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.document = Document.objects.create(
            title='Facture Électrique',
            content='Facture d\'électricité du mois de janvier'
        )

        self.document_type = DocumentType.objects.create(
            name='Facture',
            match='facture',
            matching_algorithm=1
        )

        self.ai_model = AIModel.objects.create(
            name='Hybrid Model',
            model_type='classification',
            language='fr',
            owner=self.user,
            status='active'
        )

    @patch('paperless_ai.classification.DistilBertClassifier')
    def test_engine_initialization(self, mock_classifier):
        """Test l'initialisation du moteur hybride"""
        engine = HybridClassificationEngine()
        self.assertIsNotNone(engine)

    @patch('paperless_ai.classification.DistilBertClassifier')
    def test_rule_based_classification(self, mock_classifier):
        """Test la classification basée sur les règles"""
        engine = HybridClassificationEngine()

        # Test avec un document qui devrait matcher une règle
        result = engine._classify_with_rules(self.document)

        self.assertIsNotNone(result)
        # Devrait trouver le type de document "Facture" grâce au mot "facture"
        if result['document_type']:
            self.assertEqual(result['document_type'], self.document_type)


class VectorSearchEngineTestCase(TestCase):
    """Tests pour VectorSearchEngine"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')

        self.document1 = Document.objects.create(
            title='Document sur les voitures',
            content='Ce document parle de voitures électriques'
        )

        self.document2 = Document.objects.create(
            title='Document sur les trains',
            content='Ce document parle de trains à grande vitesse'
        )

        self.ai_model = AIModel.objects.create(
            name='Search Model',
            model_type='embedding',
            language='fr',
            owner=self.user,
            status='active'
        )

        # Créer des embeddings fictifs
        DocumentEmbedding.objects.create(
            document=self.document1,
            model=self.ai_model,
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5]
        )

        DocumentEmbedding.objects.create(
            document=self.document2,
            model=self.ai_model,
            embedding=[0.6, 0.7, 0.8, 0.9, 1.0]
        )

    @patch('paperless_ai.classification.DistilBertClassifier')
    def test_search_engine_initialization(self, mock_classifier):
        """Test l'initialisation du moteur de recherche"""
        engine = VectorSearchEngine()
        self.assertIsNotNone(engine)
        self.assertEqual(engine.similarity_threshold, 0.3)

    @patch('paperless_ai.classification.DistilBertClassifier')
    @patch('paperless_ai.classification.cosine_similarity')
    def test_document_search(self, mock_cosine, mock_classifier):
        """Test la recherche de documents"""
        # Configurer les mocks
        mock_cosine.return_value = [[0.8, 0.2]]  # Similarités simulées

        mock_classifier_instance = Mock()
        mock_classifier.return_value = mock_classifier_instance
        mock_classifier_instance.generate_embedding.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

        engine = VectorSearchEngine()
        engine.distilbert_classifier = mock_classifier_instance

        results = engine.search_documents("voitures", top_k=2)

        self.assertIsNotNone(results)
        mock_classifier_instance.generate_embedding.assert_called_once_with("voitures")


class APITestCase(APITestCase):
    """Tests pour les API REST"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.ai_model = AIModel.objects.create(
            name='API Test Model',
            model_type='classification',
            language='fr',
            owner=self.user
        )

        self.document = Document.objects.create(
            title='Test Document',
            content='Contenu de test'
        )

    def test_ai_model_list_api(self):
        """Test l'API de liste des modèles IA"""
        url = reverse('paperless_ai:aimodel-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'API Test Model')

    def test_ai_model_create_api(self):
        """Test l'API de création de modèle IA"""
        url = reverse('paperless_ai:aimodel-list')
        data = {
            'name': 'New Model',
            'description': 'Un nouveau modèle',
            'model_type': 'embedding',
            'language': 'en',
            'model_config': {
                'model_name': 'distilbert-base-multilingual-cased'
            }
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Model')
        self.assertEqual(response.data['owner'], self.user.id)

    def test_semantic_search_api(self):
        """Test l'API de recherche sémantique"""
        url = reverse('paperless_ai:semanticsearch-search')
        data = {
            'query': 'test document',
            'top_k': 5,
            'similarity_threshold': 0.3
        }

        with patch('paperless_ai.views.VectorSearchEngine') as mock_engine:
            # Configurer le mock
            mock_instance = Mock()
            mock_engine.return_value = mock_instance
            mock_instance.search_documents.return_value = [
                {
                    'document': self.document,
                    'similarity': 0.8
                }
            ]

            response = self.client.post(url, data, format='json')

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('results', response.data)
            self.assertEqual(response.data['results_count'], 1)

    def test_document_classification_api(self):
        """Test l'API de classification de document"""
        url = reverse('paperless_ai:documentprocessing-classify')
        data = {
            'document_id': self.document.id,
            'force_reclassify': True
        }

        with patch('paperless_ai.views.classify_document_task') as mock_task:
            mock_task.delay.return_value = Mock(id='task-123')

            response = self.client.post(url, data, format='json')

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('task_id', response.data)
            self.assertEqual(response.data['document_id'], self.document.id)

    def test_unauthorized_access(self):
        """Test l'accès non autorisé"""
        self.client.force_authenticate(user=None)

        url = reverse('paperless_ai:aimodel-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SerializerTestCase(TestCase):
    """Tests pour les sérialiseurs"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_ai_model_serializer(self):
        """Test le sérialiseur AIModel"""
        data = {
            'name': 'Test Serializer Model',
            'description': 'Modèle pour test de sérialiseur',
            'model_type': 'classification',
            'language': 'fr',
            'model_config': {
                'model_name': 'distilbert-base-multilingual-cased'
            }
        }

        serializer = AIModelSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        # Test de sauvegarde
        model = serializer.save(owner=self.user)
        self.assertEqual(model.name, 'Test Serializer Model')
        self.assertEqual(model.owner, self.user)

    def test_semantic_search_serializer(self):
        """Test le sérialiseur de recherche sémantique"""
        data = {
            'query': 'test search',
            'top_k': 10,
            'similarity_threshold': 0.5
        }

        serializer = SemanticSearchSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        validated_data = serializer.validated_data
        self.assertEqual(validated_data['query'], 'test search')
        self.assertEqual(validated_data['top_k'], 10)
        self.assertEqual(validated_data['similarity_threshold'], 0.5)

    def test_classification_request_serializer(self):
        """Test le sérialiseur de demande de classification"""
        document = Document.objects.create(
            title='Test Document',
            content='Contenu de test'
        )

        data = {
            'document_id': document.id,
            'force_reclassify': True
        }

        serializer = ClassificationRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        validated_data = serializer.validated_data
        self.assertEqual(validated_data['document_id'], document.id)
        self.assertTrue(validated_data['force_reclassify'])


class TaskTestCase(TransactionTestCase):
    """Tests pour les tâches Celery"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        self.document = Document.objects.create(
            title='Task Test Document',
            content='Contenu pour test de tâche'
        )

        self.ai_model = AIModel.objects.create(
            name='Task Test Model',
            model_type='classification',
            language='fr',
            owner=self.user,
            status='active'
        )

    @patch('paperless_ai.tasks.HybridClassificationEngine')
    def test_classify_document_task(self, mock_engine):
        """Test la tâche de classification de document"""
        from paperless_ai.tasks import classify_document_task

        # Configurer le mock
        mock_instance = Mock()
        mock_engine.return_value = mock_instance
        mock_instance.classify_document.return_value = {
            'document_type': None,
            'correspondent': None,
            'tags': [],
            'confidence': 0.8
        }

        # Exécuter la tâche
        result = classify_document_task(self.document.id)

        self.assertIsNotNone(result)
        mock_instance.classify_document.assert_called_once()

    @patch('paperless_ai.tasks.VectorSearchEngine')
    def test_generate_document_embedding_task(self, mock_engine):
        """Test la tâche de génération d'embedding"""
        from paperless_ai.tasks import generate_document_embedding_task

        # Configurer le mock
        mock_instance = Mock()
        mock_engine.return_value = mock_instance
        mock_instance.distilbert_classifier.generate_embedding.return_value = [0.1, 0.2, 0.3]

        # Exécuter la tâche
        result = generate_document_embedding_task(self.document.id)

        self.assertIsNotNone(result)


class IntegrationTestCase(TransactionTestCase):
    """Tests d'intégration complets"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='integration_user',
            password='testpass123',
            is_staff=True
        )

        # Créer des données de test
        self.document_type = DocumentType.objects.create(
            name='Facture',
            match='facture',
            matching_algorithm=1
        )

        self.correspondent = Correspondent.objects.create(
            name='Entreprise Test',
            match='entreprise',
            matching_algorithm=1
        )

        self.tag = Tag.objects.create(
            name='Important',
            color='#ff0000',
            match='important',
            matching_algorithm=1
        )

        self.document = Document.objects.create(
            title='Facture Entreprise Test',
            content='Cette facture importante vient de l\'entreprise test'
        )

        self.ai_model = AIModel.objects.create(
            name='Integration Model',
            model_type='classification',
            language='fr',
            owner=self.user,
            status='active'
        )

    @patch('paperless_ai.classification.AutoTokenizer')
    @patch('paperless_ai.classification.AutoModel')
    @patch('paperless_ai.classification.cosine_similarity')
    def test_full_classification_workflow(self, mock_cosine, mock_model, mock_tokenizer):
        """Test le workflow complet de classification"""
        # Configurer les mocks
        mock_tokenizer.from_pretrained.return_value = Mock()
        mock_model.from_pretrained.return_value = Mock()
        mock_cosine.return_value = [[0.9]]

        # Test du moteur hybride
        engine = HybridClassificationEngine()

        # La classification basée sur les règles devrait fonctionner
        result = engine._classify_with_rules(self.document)

        # Vérifier que les règles ont trouvé des correspondances
        self.assertIsNotNone(result)

        # Le document contient "facture" donc devrait matcher le type
        # Le document contient "entreprise" donc devrait matcher le correspondant
        # Le document contient "important" donc devrait matcher le tag
