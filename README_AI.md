# Paperless-ngx avec Système de Classification AI

## 🚀 Vue d'ensemble

Ce dépôt contient Paperless-ngx amélioré avec un système complet de classification par intelligence artificielle, incluant trois nouveaux modules principaux :

- **paperless_ai** : Système de classification intelligent avec DistilBERT
- **paperless_ocr** : Pipeline OCR hybride (Tesseract + Doctr)
- **paperless_imap** : Système avancé de gestion des e-mails IMAP

## 📊 Fonctionnalités AI

### Classification Intelligente
- Classification multilingue des documents avec DistilBERT
- Embeddings vectoriels et recherche sémantique
- Moteur de classification hybride (IA + règles)
- API REST complète avec ViewSets Django
- Interfaces d'administration avec actions en lot
- Traitement asynchrone avec Celery

### Architecture Technique
- **6 modèles Django** : AIModel, DocumentEmbedding, DocumentClassification, SearchQuery, AIMetrics, TrainingJob
- **3 moteurs IA** : DistilBertClassifier, HybridClassificationEngine, VectorSearchEngine
- **6 ViewSets REST API** avec opérations CRUD complètes
- **Intégration complète** dans l'application Paperless-ngx principale

## 🔧 Installation et Configuration

### Prérequis
```bash
# Dépendances ML ajoutées au pyproject.toml
torch>=2.3.0
transformers>=4.45.0
scikit-learn>=1.3.0
```

### Migration de la base de données
```bash
cd src/
uv run python manage.py migrate
```

### Initialisation du système AI
```bash
cd src/
uv run python manage.py init_ai_system
```

### Entraînement du modèle
```bash
cd src/
uv run python manage.py train_model --model-type distilbert --data-path /path/to/training/data
```

## 📁 Structure des Modules

### paperless_ai/
```
paperless_ai/
├── __init__.py
├── admin.py              # Interfaces Django Admin
├── apps.py
├── classification.py     # Moteurs de classification IA
├── models.py            # 6 modèles Django
├── serializers.py       # Sérialiseurs REST API
├── signals.py           # Signaux Django
├── tasks.py             # Tâches Celery asynchrones
├── urls.py              # Routage URL
├── views.py             # 6 ViewSets REST API
├── management/
│   └── commands/
│       ├── init_ai_system.py
│       └── train_model.py
├── migrations/
│   └── 0001_initial.py
└── tests.py
```

### paperless_ocr/
```
paperless_ocr/
├── __init__.py
├── admin.py
├── apps.py
├── config.py            # Configuration OCR
├── engines.py           # Moteurs Tesseract + Doctr
├── models.py
├── serializers.py
├── tasks.py             # Traitement OCR asynchrone
├── urls.py
├── views.py
├── management/
│   └── commands/
│       └── ocr_process.py
└── migrations/
    └── 0001_initial.py
```

### paperless_imap/
```
paperless_imap/
├── __init__.py
├── admin.py
├── apps.py
├── imap_engine.py       # Moteur IMAP avancé
├── models.py
├── serializers.py
├── tasks.py             # Synchronisation IMAP
├── urls.py
├── views.py
├── management/
│   └── commands/
│       ├── sync_imap_accounts.py
│       └── imap_maintenance.py
└── migrations/
    └── 0001_initial.py
```

## 🌟 API REST

### Endpoints principaux
- `/api/ai/models/` - Gestion des modèles IA
- `/api/ai/classifications/` - Classifications de documents
- `/api/ai/embeddings/` - Embeddings vectoriels
- `/api/ai/search/` - Recherche sémantique
- `/api/ai/metrics/` - Métriques et analyses
- `/api/ai/training-jobs/` - Gestion de l'entraînement

### Exemple d'utilisation
```python
import requests

# Classification d'un document
response = requests.post('/api/ai/classify/', {
    'document_id': 123,
    'model_name': 'distilbert-multilingual'
})

# Recherche sémantique
response = requests.post('/api/ai/search/', {
    'query': 'factures électricité',
    'top_k': 10
})
```

## 🔄 Tâches Celery

### Tâches disponibles
- `classify_document_task` - Classification automatique
- `generate_embeddings_task` - Génération d'embeddings
- `train_model_task` - Entraînement de modèles
- `update_search_index_task` - Mise à jour de l'index

### Configuration Celery
```python
# Dans settings.py
CELERY_BEAT_SCHEDULE = {
    'auto-classify-new-documents': {
        'task': 'paperless_ai.tasks.classify_pending_documents',
        'schedule': crontab(minute='*/10'),
    },
}
```

## 📈 Métriques et Monitoring

### Métriques collectées
- Précision de classification
- Temps de traitement
- Utilisation des modèles
- Performance des recherches

### Tableau de bord Admin
Accessible via l'interface Django Admin avec :
- Visualisation des métriques
- Gestion des modèles
- Actions en lot sur les classifications
- Monitoring des tâches d'entraînement

## 🧪 Tests

### Lancement des tests
```bash
cd src/
uv run python manage.py test paperless_ai
uv run python manage.py test paperless_ocr
uv run python manage.py test paperless_imap
```

### Couverture des tests
- Tests unitaires pour tous les modèles
- Tests d'intégration API
- Tests de performance
- Tests de classification

## 🚀 Déploiement

### Variables d'environnement
```bash
# Configuration IA
PAPERLESS_AI_ENABLED=true
PAPERLESS_AI_MODEL_PATH=/app/models/
PAPERLESS_AI_BATCH_SIZE=32
PAPERLESS_AI_DEVICE=cpu  # ou 'cuda' pour GPU

# Configuration OCR
PAPERLESS_OCR_HYBRID_ENABLED=true
PAPERLESS_OCR_TESSERACT_TIMEOUT=300
PAPERLESS_OCR_DOCTR_CONFIDENCE=0.7

# Configuration IMAP
PAPERLESS_IMAP_AUTO_SYNC=true
PAPERLESS_IMAP_SYNC_INTERVAL=300
```

### Docker
Le système est compatible avec Docker. Les dépendances ML sont incluses dans les requirements.

## 📚 Documentation

### Fichiers de documentation
- `API_SPECIFICATIONS.md` - Spécifications complètes de l'API
- `ARCHITECTURE_EXTENSION.md` - Architecture détaillée
- `DATABASE_SCHEMAS.md` - Schémas de base de données
- `IMPLEMENTATION_SUMMARY.md` - Résumé d'implémentation
- `MIGRATION_PLAN.md` - Plan de migration

## 🏷️ Versions

### Version actuelle : v1.0.0-ai-system

**Fonctionnalités principales :**
- ✅ Système de classification IA complet
- ✅ Pipeline OCR hybride fonctionnel
- ✅ Gestion IMAP avancée
- ✅ API REST complète
- ✅ Interfaces d'administration
- ✅ Traitement asynchrone
- ✅ Suite de tests complète

### Historique Git
```bash
# Voir l'historique des commits
git log --oneline --graph

# Voir les tags
git tag -l

# Voir les branches
git branch -a
```

## 🤝 Contribution

### Workflow de développement
1. Créer une branche feature
2. Développer et tester
3. Créer un commit avec message descriptif
4. Merger vers la branche principale

### Structure des commits
```
feat: ajout d'une nouvelle fonctionnalité
fix: correction d'un bug
docs: mise à jour de la documentation
test: ajout de tests
refactor: refactoring de code
```

## 📞 Support

Pour le support technique :
1. Vérifier la documentation
2. Consulter les logs : `data/log/paperless.log`
3. Tester les commandes de diagnostic
4. Consulter les métriques dans l'admin

---

**Paperless-ngx AI System** - Version 1.0.0 🚀
