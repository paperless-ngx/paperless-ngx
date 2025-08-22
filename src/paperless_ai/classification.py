"""
Moteur de classification intelligent basé sur DistilBERT

Classification sémantique de documents, prédiction de correspondants,
suggestion de tags et génération d'embeddings.
"""

import os
import json
import logging
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import pickle

import torch
from transformers import (
    DistilBertTokenizer, DistilBertForSequenceClassification,
    DistilBertModel, AutoTokenizer, AutoModel
)
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report

from django.conf import settings
from django.utils import timezone
from documents.models import Document, DocumentType, Correspondent, Tag

from .models import (
    AIModel, DocumentEmbedding, DocumentClassification,
    TrainingJob, AIMetrics
)


logger = logging.getLogger(__name__)


class DistilBertClassifier:
    """Classificateur basé sur DistilBERT pour documents"""

    def __init__(self, model_name: str = "distilbert-base-multilingual-cased"):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.label_encoder = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.max_length = 512
        self.batch_size = 16

        # Chemins de stockage
        self.models_dir = Path(settings.MEDIA_ROOT) / "ai_models"
        self.models_dir.mkdir(exist_ok=True)

    def load_model(self, model_path: str = None):
        """Charge un modèle pré-entraîné"""
        try:
            if model_path and os.path.exists(model_path):
                # Charger modèle personnalisé
                self.model = DistilBertForSequenceClassification.from_pretrained(model_path)
                self.tokenizer = DistilBertTokenizer.from_pretrained(model_path)

                # Charger l'encodeur de labels
                label_encoder_path = os.path.join(model_path, "label_encoder.pkl")
                if os.path.exists(label_encoder_path):
                    with open(label_encoder_path, 'rb') as f:
                        self.label_encoder = pickle.load(f)
            else:
                # Charger modèle de base
                self.tokenizer = DistilBertTokenizer.from_pretrained(self.model_name)
                self.model = DistilBertModel.from_pretrained(self.model_name)

            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Modèle chargé avec succès: {model_path or self.model_name}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle: {e}")
            raise

    def preprocess_text(self, text: str) -> str:
        """Prétraitement du texte"""
        if not text:
            return ""

        # Nettoyage de base
        text = text.strip()
        text = " ".join(text.split())  # Normalise les espaces

        # Limitation de longueur
        if len(text) > 10000:  # Limite arbitraire
            text = text[:10000]

        return text

    def generate_embedding(self, text: str) -> np.ndarray:
        """Génère un embedding pour un texte"""
        if not self.model or not self.tokenizer:
            raise ValueError("Modèle non chargé")

        text = self.preprocess_text(text)

        # Tokenisation
        inputs = self.tokenizer(
            text,
            max_length=self.max_length,
            padding=True,
            truncation=True,
            return_tensors="pt"
        )

        # Déplacer vers le device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Génération de l'embedding
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Utiliser la représentation [CLS] token
            embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()

        return embedding.flatten()

    def classify_document_type(self, text: str, confidence_threshold: float = 0.8) -> Dict[str, Any]:
        """Classifie le type de document"""
        try:
            if not self.model or not self.label_encoder:
                return {"error": "Modèle de classification non disponible"}

            embedding = self.generate_embedding(text)

            # Prédiction
            inputs = self.tokenizer(
                self.preprocess_text(text),
                max_length=self.max_length,
                padding=True,
                truncation=True,
                return_tensors="pt"
            )

            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
                predicted_class_id = torch.argmax(probabilities, dim=-1).item()
                confidence = probabilities.max().item()

            if confidence < confidence_threshold:
                return {
                    "predicted_class": None,
                    "confidence": confidence,
                    "message": "Confiance insuffisante"
                }

            predicted_class = self.label_encoder.inverse_transform([predicted_class_id])[0]

            return {
                "predicted_class": predicted_class,
                "confidence": confidence,
                "embedding": embedding.tolist()
            }

        except Exception as e:
            logger.error(f"Erreur lors de la classification: {e}")
            return {"error": str(e)}

    def suggest_correspondent(self, text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Suggère des correspondants basés sur le contenu"""
        try:
            # Générer embedding du document
            doc_embedding = self.generate_embedding(text)

            # Récupérer tous les correspondants avec embeddings
            correspondents = []
            for correspondent in Correspondent.objects.all():
                # Calculer embedding moyen des documents du correspondant
                documents = Document.objects.filter(correspondent=correspondent)[:10]  # Limite pour performance

                if not documents:
                    continue

                embeddings = []
                for doc in documents:
                    try:
                        embedding_obj = DocumentEmbedding.objects.get(document=doc)
                        embeddings.append(embedding_obj.get_vector_array())
                    except DocumentEmbedding.DoesNotExist:
                        continue

                if embeddings:
                    # Calculer embedding moyen
                    avg_embedding = np.mean(embeddings, axis=0)

                    # Calculer similarité
                    similarity = cosine_similarity(
                        doc_embedding.reshape(1, -1),
                        avg_embedding.reshape(1, -1)
                    )[0][0]

                    correspondents.append({
                        "correspondent": correspondent,
                        "similarity": similarity,
                        "sample_count": len(embeddings)
                    })

            # Trier par similarité
            correspondents.sort(key=lambda x: x["similarity"], reverse=True)

            return correspondents[:top_k]

        except Exception as e:
            logger.error(f"Erreur lors de la suggestion de correspondant: {e}")
            return []

    def suggest_tags(self, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Suggère des tags basés sur le contenu"""
        try:
            # Générer embedding du document
            doc_embedding = self.generate_embedding(text)

            # Récupérer tous les tags avec embeddings
            tags = []
            for tag in Tag.objects.all():
                # Calculer embedding moyen des documents avec ce tag
                documents = Document.objects.filter(tags=tag)[:10]  # Limite pour performance

                if not documents:
                    continue

                embeddings = []
                for doc in documents:
                    try:
                        embedding_obj = DocumentEmbedding.objects.get(document=doc)
                        embeddings.append(embedding_obj.get_vector_array())
                    except DocumentEmbedding.DoesNotExist:
                        continue

                if embeddings:
                    # Calculer embedding moyen
                    avg_embedding = np.mean(embeddings, axis=0)

                    # Calculer similarité
                    similarity = cosine_similarity(
                        doc_embedding.reshape(1, -1),
                        avg_embedding.reshape(1, -1)
                    )[0][0]

                    tags.append({
                        "tag": tag,
                        "similarity": similarity,
                        "sample_count": len(embeddings)
                    })

            # Trier par similarité
            tags.sort(key=lambda x: x["similarity"], reverse=True)

            return tags[:top_k]

        except Exception as e:
            logger.error(f"Erreur lors de la suggestion de tags: {e}")
            return []


class HybridClassificationEngine:
    """Moteur de classification hybride combinant règles et IA"""

    def __init__(self):
        self.distilbert_classifier = DistilBertClassifier()
        self.confidence_threshold = 0.8
        self.rule_weight = 0.3
        self.ai_weight = 0.7

    def load_models(self):
        """Charge tous les modèles nécessaires"""
        try:
            # Charger le modèle principal
            ai_models = AIModel.objects.filter(status='ready')

            for ai_model in ai_models:
                if ai_model.model_type == 'classification':
                    self.distilbert_classifier.load_model(ai_model.model_path)
                    break
            else:
                # Charger modèle de base si aucun modèle entraîné
                self.distilbert_classifier.load_model()

            logger.info("Modèles hybrides chargés avec succès")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des modèles: {e}")
            raise

    def classify_document(self, document: Document) -> Dict[str, Any]:
        """Classification complète d'un document"""
        try:
            # Extraire le texte du document
            text = self._extract_document_text(document)

            if not text:
                return {"error": "Impossible d'extraire le texte du document"}

            # Classification IA
            ai_result = self.distilbert_classifier.classify_document_type(text)

            # Classification par règles (logique Paperless existante)
            rule_result = self._apply_rules_classification(document, text)

            # Combinaison des résultats
            final_result = self._combine_results(ai_result, rule_result)

            # Enregistrer la classification
            self._save_classification(document, final_result)

            return final_result

        except Exception as e:
            logger.error(f"Erreur lors de la classification du document {document.id}: {e}")
            return {"error": str(e)}

    def _extract_document_text(self, document: Document) -> str:
        """Extrait le texte du document"""
        try:
            # Utiliser le contenu existant si disponible
            if hasattr(document, 'content') and document.content:
                return document.content

            # Fallback sur le titre et autres métadonnées
            text_parts = []

            if document.title:
                text_parts.append(document.title)

            if document.correspondent:
                text_parts.append(f"Correspondant: {document.correspondent.name}")

            if document.document_type:
                text_parts.append(f"Type: {document.document_type.name}")

            # Ajouter les tags
            for tag in document.tags.all():
                text_parts.append(f"Tag: {tag.name}")

            return " ".join(text_parts)

        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de texte: {e}")
            return ""

    def _apply_rules_classification(self, document: Document, text: str) -> Dict[str, Any]:
        """Applique les règles de classification traditionnelles"""
        try:
            # Logique simplifiée des règles Paperless
            predictions = {
                "document_type": None,
                "correspondent": None,
                "tags": [],
                "confidence": 0.5  # Confiance par défaut pour les règles
            }

            # Règles basées sur le nom de fichier
            filename = document.original_filename or ""

            # Règles pour les types de documents
            if any(word in filename.lower() for word in ['facture', 'invoice', 'bill']):
                try:
                    invoice_type = DocumentType.objects.get(name__icontains="facture")
                    predictions["document_type"] = invoice_type
                    predictions["confidence"] = 0.8
                except DocumentType.DoesNotExist:
                    pass

            elif any(word in filename.lower() for word in ['contrat', 'contract']):
                try:
                    contract_type = DocumentType.objects.get(name__icontains="contrat")
                    predictions["document_type"] = contract_type
                    predictions["confidence"] = 0.8
                except DocumentType.DoesNotExist:
                    pass

            # Règles pour les correspondants basées sur le contenu
            text_lower = text.lower()
            for correspondent in Correspondent.objects.all()[:20]:  # Limite pour performance
                if correspondent.name.lower() in text_lower:
                    predictions["correspondent"] = correspondent
                    predictions["confidence"] = min(predictions["confidence"] + 0.3, 1.0)
                    break

            return predictions

        except Exception as e:
            logger.error(f"Erreur lors de l'application des règles: {e}")
            return {"confidence": 0.0}

    def _combine_results(self, ai_result: Dict, rule_result: Dict) -> Dict[str, Any]:
        """Combine les résultats IA et règles"""
        try:
            combined = {
                "document_type": None,
                "correspondent": None,
                "tags": [],
                "confidence": 0.0,
                "method": "hybrid",
                "ai_confidence": ai_result.get("confidence", 0.0),
                "rule_confidence": rule_result.get("confidence", 0.0)
            }

            # Pondération des confiances
            ai_conf = ai_result.get("confidence", 0.0) * self.ai_weight
            rule_conf = rule_result.get("confidence", 0.0) * self.rule_weight

            combined["confidence"] = ai_conf + rule_conf

            # Sélection du meilleur résultat pour chaque catégorie
            if ai_conf > rule_conf:
                # Privilégier IA
                if "predicted_class" in ai_result and ai_result["predicted_class"]:
                    try:
                        doc_type = DocumentType.objects.get(name=ai_result["predicted_class"])
                        combined["document_type"] = doc_type
                    except DocumentType.DoesNotExist:
                        pass

                combined["method"] = "ai_primary"
            else:
                # Privilégier règles
                combined["document_type"] = rule_result.get("document_type")
                combined["correspondent"] = rule_result.get("correspondent")
                combined["method"] = "rules_primary"

            # Combiner les tags
            combined["tags"] = rule_result.get("tags", [])

            return combined

        except Exception as e:
            logger.error(f"Erreur lors de la combinaison des résultats: {e}")
            return {"confidence": 0.0, "error": str(e)}

    def _save_classification(self, document: Document, result: Dict):
        """Enregistre la classification en base"""
        try:
            if result.get("confidence", 0) < 0.3:
                return  # Ne pas enregistrer les classifications peu fiables

            # Récupérer ou créer le modèle IA
            ai_model, created = AIModel.objects.get_or_create(
                name="hybrid_classifier",
                defaults={
                    "model_type": "classification",
                    "model_path": "hybrid",
                    "status": "ready",
                    "owner_id": 1  # Admin par défaut
                }
            )

            # Créer la classification
            classification = DocumentClassification.objects.create(
                document=document,
                model=ai_model,
                classification_type="document_type",
                predicted_class=str(result.get("document_type", "unknown")),
                confidence_score=result.get("confidence", 0.0),
                predicted_document_type=result.get("document_type"),
                predicted_correspondent=result.get("correspondent"),
                features_used={
                    "method": result.get("method"),
                    "ai_confidence": result.get("ai_confidence"),
                    "rule_confidence": result.get("rule_confidence")
                }
            )

            # Ajouter les tags prédits
            if result.get("tags"):
                classification.predicted_tags.set(result.get("tags"))

            logger.info(f"Classification sauvegardée pour document {document.id}")

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de classification: {e}")


class VectorSearchEngine:
    """Moteur de recherche vectorielle pour la recherche sémantique"""

    def __init__(self):
        self.embedding_model = DistilBertClassifier()
        self.similarity_threshold = 0.3

    def load_model(self):
        """Charge le modèle d'embedding"""
        try:
            self.embedding_model.load_model()
            logger.info("Modèle de recherche vectorielle chargé")
        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle de recherche: {e}")
            raise

    def search_documents(self, query: str, top_k: int = 20, filters: Dict = None) -> List[Dict]:
        """Recherche sémantique de documents"""
        try:
            # Générer embedding de la requête
            query_embedding = self.embedding_model.generate_embedding(query)

            # Récupérer tous les embeddings de documents
            document_embeddings = DocumentEmbedding.objects.select_related('document')

            if filters:
                # Appliquer les filtres
                if filters.get('document_type'):
                    document_embeddings = document_embeddings.filter(
                        document__document_type=filters['document_type']
                    )
                if filters.get('correspondent'):
                    document_embeddings = document_embeddings.filter(
                        document__correspondent=filters['correspondent']
                    )
                if filters.get('tags'):
                    document_embeddings = document_embeddings.filter(
                        document__tags__in=filters['tags']
                    )

            # Calculer les similarités
            results = []
            for doc_emb in document_embeddings:
                try:
                    doc_vector = doc_emb.get_vector_array()
                    similarity = cosine_similarity(
                        query_embedding.reshape(1, -1),
                        doc_vector.reshape(1, -1)
                    )[0][0]

                    if similarity >= self.similarity_threshold:
                        results.append({
                            "document": doc_emb.document,
                            "similarity": similarity,
                            "embedding_id": doc_emb.id
                        })

                except Exception as e:
                    logger.warning(f"Erreur avec embedding {doc_emb.id}: {e}")
                    continue

            # Trier par similarité
            results.sort(key=lambda x: x["similarity"], reverse=True)

            return results[:top_k]

        except Exception as e:
            logger.error(f"Erreur lors de la recherche vectorielle: {e}")
            return []

    def generate_document_embedding(self, document: Document) -> bool:
        """Génère et sauvegarde l'embedding d'un document"""
        try:
            # Extraire le texte
            text = self._extract_document_text(document)

            if not text:
                logger.warning(f"Pas de texte extrait pour le document {document.id}")
                return False

            # Générer l'embedding
            embedding_vector = self.embedding_model.generate_embedding(text)

            # Récupérer ou créer le modèle d'embedding
            ai_model, created = AIModel.objects.get_or_create(
                name="document_embedder",
                defaults={
                    "model_type": "embedding",
                    "model_path": "distilbert-base-multilingual-cased",
                    "status": "ready",
                    "owner_id": 1
                }
            )

            # Sauvegarder l'embedding
            doc_embedding, created = DocumentEmbedding.objects.update_or_create(
                document=document,
                model=ai_model,
                defaults={
                    "embedding_vector": embedding_vector.tolist(),
                    "vector_dimension": len(embedding_vector),
                    "text_length": len(text),
                    "extraction_method": "full_text"
                }
            )

            logger.info(f"Embedding généré pour document {document.id}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embedding pour {document.id}: {e}")
            return False

    def _extract_document_text(self, document: Document) -> str:
        """Extrait le texte du document pour l'embedding"""
        text_parts = []

        if document.title:
            text_parts.append(document.title)

        if hasattr(document, 'content') and document.content:
            text_parts.append(document.content)

        if document.correspondent:
            text_parts.append(document.correspondent.name)

        if document.document_type:
            text_parts.append(document.document_type.name)

        # Ajouter les tags
        for tag in document.tags.all():
            text_parts.append(tag.name)

        return " ".join(text_parts)
