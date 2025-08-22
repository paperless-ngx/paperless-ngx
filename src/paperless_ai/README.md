# Module de Classification Intelligente - Paperless-ngx

Le module `paperless_ai` apporte des capacités d'intelligence artificielle avancées à Paperless-ngx, notamment :

- **Classification automatique** des documents avec DistilBERT
- **Recherche sémantique** vectorielle
- **Système hybride** combinant règles et IA
- **Prédiction de correspondants** et suggestion de tags
- **Métriques de performance** et monitoring

## 🚀 Fonctionnalités

### Classification Automatique
- Prédiction du type de document
- Identification du correspondant
- Suggestion de tags pertinents
- Score de confiance pour chaque prédiction

### Recherche Sémantique
- Recherche par similarité vectorielle
- Recherche multilingue (français/anglais)
- Filtres avancés combinables
- Résultats classés par pertinence

### Système Hybride
- Combine classification par règles existantes et IA
- Fallback intelligent en cas d'échec IA
- Configuration flexible des seuils de confiance
- Optimisation des performances

### Monitoring et Métriques
- Suivi des performances en temps réel
- Métriques de précision, rappel, F1-score
- Temps de réponse et throughput
- Tableaux de bord de monitoring

## 📋 Prérequis

### Dépendances Python
```bash
# Déjà incluses dans pyproject.toml
torch>=2.3.0
transformers>=4.45.0
scikit-learn~=1.7.0
```

### Configuration Système
- **RAM** : 4GB minimum, 8GB recommandé
- **CPU** : Multi-core recommandé pour le parallélisme
- **GPU** : Optionnel, accélère l'inférence
- **Stockage** : ~2GB pour les modèles DistilBERT

## 🛠️ Installation et Configuration

### 1. Activation du Module
Le module est automatiquement activé via `INSTALLED_APPS` dans `settings.py`.

### 2. Migrations
```bash
cd src
uv run python manage.py migrate paperless_ai
```

### 3. Initialisation du Système IA
```bash
# Créer les modèles par défaut
uv run python manage.py init_ai_system --create-default-models

# Générer les embeddings pour documents existants
uv run python manage.py init_ai_system --generate-embeddings

# Lancer la classification automatique
uv run python manage.py init_ai_system --classify-documents

# Tout faire en une fois
uv run python manage.py init_ai_system
```

### 4. Configuration des Workers Celery
Pour le traitement en arrière-plan, assurez-vous que Celery tourne :
```bash
# Dans un terminal séparé
cd src
uv run celery --app paperless worker -l INFO
```

## 🎯 Utilisation

### API REST

#### Recherche Sémantique
```bash
# Recherche de documents
curl -X POST http://localhost:8000/api/ai/search/search/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_TOKEN" \
  -d '{
    "query": "facture électricité",
    "top_k": 10,
    "similarity_threshold": 0.3
  }'
```

#### Classification de Document
```bash
# Classifier un document
curl -X POST http://localhost:8000/api/ai/processing/classify/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_TOKEN" \
  -d '{
    "document_id": 123,
    "force_reclassify": false
  }'
```

#### Suggestions pour Document
```bash
# Obtenir des suggestions
curl -X POST http://localhost:8000/api/ai/search/suggest/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_TOKEN" \
  -d '{
    "document_id": 123,
    "suggestion_types": ["correspondent", "tags"],
    "max_suggestions": 5,
    "min_confidence": 0.3
  }'
```

### Interface d'Administration

Accédez à `/admin/paperless_ai/` pour :
- Gérer les modèles IA
- Valider les classifications
- Consulter les métriques
- Surveiller les tâches d'entraînement

### Commandes de Gestion

#### Entraînement de Modèle
```bash
# Entraîner un modèle spécifique
uv run python manage.py train_model 1 \
  --epochs 5 \
  --batch-size 32 \
  --learning-rate 1e-5 \
  --use-validated-only \
  --wait
```

#### Traitement par Lots
```bash
# Classifier tous les documents sans classification
uv run python manage.py init_ai_system --classify-documents --batch-size 100

# Générer les embeddings manquants
uv run python manage.py init_ai_system --generate-embeddings --batch-size 50
```

## ⚙️ Configuration Avancée

### Variables d'Environnement
```bash
# Traitement automatique des nouveaux documents
export PAPERLESS_AI_AUTO_PROCESS_UPDATES=true

# Seuil de confiance par défaut
export PAPERLESS_AI_DEFAULT_CONFIDENCE=0.8

# Utilisation du GPU si disponible
export PAPERLESS_AI_USE_GPU=true
```

### Configuration des Modèles
Les modèles peuvent être configurés via l'admin Django ou l'API :

```python
# Configuration exemple pour DistilBERT
{
    "model_name": "distilbert-base-multilingual-cased",
    "max_length": 512,
    "use_cuda": true,
    "batch_size": 16,
    "learning_rate": 2e-5,
    "confidence_threshold": 0.8
}
```

### Optimisation des Performances

#### Pour Serveurs Modestes
```python
# Réduire la taille des lots
config["batch_size"] = 8

# Utiliser CPU uniquement
config["use_cuda"] = false

# Limiter la longueur des sequences
config["max_length"] = 256
```

#### Pour Serveurs Puissants
```python
# Augmenter la taille des lots
config["batch_size"] = 32

# Utiliser GPU si disponible
config["use_cuda"] = true

# Traitement parallèle
config["num_workers"] = 4
```

## 📊 Métriques et Monitoring

### Métriques Disponibles
- **Précision** : Pourcentage de prédictions correctes
- **Rappel** : Pourcentage d'éléments pertinents trouvés
- **Score F1** : Moyenne harmonique précision/rappel
- **Temps de réponse** : Latence moyenne des requêtes
- **Throughput** : Nombre de documents traités par minute

### Tableaux de Bord
- Dashboard admin avec graphiques en temps réel
- Métriques par modèle et par période
- Alertes en cas de dégradation des performances
- Historique des entraînements

## 🔧 Développement et Extension

### Structure du Module
```
paperless_ai/
├── models.py              # Modèles de données
├── classification.py      # Moteurs de classification
├── serializers.py         # Sérialiseurs API REST
├── views.py               # Vues API
├── admin.py               # Interface d'administration
├── tasks.py               # Tâches Celery
├── signals.py             # Signaux Django
├── urls.py                # Configuration des URLs
├── tests.py               # Tests unitaires
└── management/
    └── commands/
        ├── init_ai_system.py
        └── train_model.py
```

### Ajouter un Nouveau Type de Classification
1. Étendre `MODEL_TYPES` dans `models.py`
2. Implémenter la logique dans `classification.py`
3. Ajouter les vues API correspondantes
4. Créer les tests appropriés

### Ajouter un Nouveau Modèle ML
1. Créer une classe héritant de `BaseClassifier`
2. Implémenter les méthodes requises
3. Intégrer dans `HybridClassificationEngine`
4. Ajouter la configuration par défaut

## 🐛 Dépannage

### Problèmes Courants

#### Erreur "CUDA out of memory"
```python
# Solution : Réduire batch_size
config["batch_size"] = 4
config["use_cuda"] = false
```

#### Temps de réponse lents
```python
# Solutions :
# 1. Réduire max_length
config["max_length"] = 256

# 2. Utiliser un modèle plus petit
config["model_name"] = "distilbert-base-uncased"

# 3. Activer le cache
config["use_cache"] = true
```

#### Classifications incorrectes
1. Vérifier les données d'entraînement
2. Ajuster les seuils de confiance
3. Revalider les classifications existantes
4. Relancer l'entraînement avec plus de données

### Logs et Debugging
```bash
# Activer les logs détaillés
export PAPERLESS_AI_LOG_LEVEL=DEBUG

# Consulter les logs Celery
tail -f /path/to/celery.log

# Vérifier le statut des tâches
uv run python manage.py shell
>>> from paperless_ai.models import TrainingJob
>>> TrainingJob.objects.filter(status='running')
```

## 📚 Références

- [Documentation DistilBERT](https://huggingface.co/distilbert-base-multilingual-cased)
- [Guide Transformers](https://huggingface.co/transformers/)
- [Paperless-ngx API](https://docs.paperless-ngx.com/api/)
- [Celery Documentation](https://docs.celeryproject.org/)

## 🤝 Contribution

Pour contribuer au module :
1. Fork le repository
2. Créer une branche feature
3. Implémenter les changements avec tests
4. Soumettre une pull request

## 📄 Licence

Ce module fait partie de Paperless-ngx et suit la même licence GPL-3.0.
