# Architecture Technique - Extension Paperless-ngx

## Table des matières
1. [Vue d'ensemble](#vue-densemble)
2. [Architecture existante](#architecture-existante)
3. [Modules d'extension](#modules-dextension)
4. [APIs REST](#apis-rest)
5. [Structure de base de données](#structure-de-base-de-données)
6. [Gestion des ressources](#gestion-des-ressources)
7. [Plan de migration](#plan-de-migration)
8. [Diagrammes d'architecture](#diagrammes-darchitecture)

## Vue d'ensemble

L'extension de Paperless-ngx vise à intégrer des capacités d'IA avancées tout en maintenant la compatibilité avec l'écosystème existant. Les nouveaux composants s'intègrent de manière modulaire dans l'architecture Django/Angular existante.

### Objectifs architecturaux
- **Modularité** : Activation/désactivation des fonctionnalités par configuration
- **Compatibilité** : Préservation de l'API existante
- **Performance** : Optimisation pour déploiement local
- **Scalabilité** : Support multi-threading pour traitement en arrière-plan

## Architecture existante

### Backend Django (src/)
- **documents/** : Module principal de gestion des documents
- **paperless_tesseract/** : Parser OCR Tesseract/OCRmyPDF
- **paperless_text/** : Parser texte brut
- **paperless_mail/** : Gestion des e-mails IMAP
- **paperless_tika/** : Parser Apache Tika

### Frontend Angular (src-ui/)
- Architecture modulaire avec composants réutilisables
- Communication via API REST
- Système de permissions granulaire

### Base de données
- **SQLite** (dev) / **PostgreSQL/MariaDB** (prod)
- Modèles principaux : Document, Tag, Correspondent, DocumentType, StoragePath
- Système de permissions avec django-guardian

### Système de tâches
- **Celery** avec Redis comme broker
- Traitement asynchrone des documents
- Monitoring et gestion d'erreurs

## Modules d'extension

### 1. Pipeline OCR Hybride (paperless_ai_ocr/)

```
paperless_ai_ocr/
├── __init__.py
├── apps.py
├── models.py          # Configuration OCR
├── parsers.py         # AdvancedOCRParser
├── engines/
│   ├── tesseract.py   # Interface Tesseract existante
│   ├── doctr.py       # Nouveau moteur Doctr
│   └── hybrid.py      # Logique de fusion
├── tasks.py           # Tâches Celery OCR
└── tests/
```

#### Modèles de données
```python
class OCRConfiguration(models.Model):
    name = models.CharField(max_length=128)
    primary_engine = models.CharField(choices=[('tesseract', 'Tesseract'), ('doctr', 'Doctr')])
    secondary_engine = models.CharField(choices=[('tesseract', 'Tesseract'), ('doctr', 'Doctr')])
    fusion_strategy = models.CharField(choices=[('confidence', 'Confidence'), ('voting', 'Voting')])
    confidence_threshold = models.FloatField(default=0.8)
    enabled = models.BooleanField(default=True)

class OCRResult(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    engine = models.CharField(max_length=64)
    confidence = models.FloatField()
    raw_text = models.TextField()
    bounding_boxes = models.JSONField()
    processing_time = models.FloatField()
    created = models.DateTimeField(auto_now_add=True)
```

### 2. Moteur IA Local (paperless_ai_engine/)

```
paperless_ai_engine/
├── __init__.py
├── apps.py
├── models.py          # Configuration IA
├── engines/
│   ├── embeddings.py  # DistilBERT/Sentence-BERT
│   ├── llm.py         # LLaMA 3 local
│   └── classification.py # Améliorations classifieur
├── tasks.py           # Tâches IA asynchrones
├── vector_store.py    # Interface base vectorielle
└── utils.py
```

#### Modèles de données
```python
class AIConfiguration(models.Model):
    embedding_model = models.CharField(max_length=256, default='distilbert-base-multilingual-cased')
    llm_model_path = models.CharField(max_length=512)
    vector_dimension = models.IntegerField(default=768)
    similarity_threshold = models.FloatField(default=0.7)
    enabled = models.BooleanField(default=True)

class DocumentEmbedding(models.Model):
    document = models.OneToOneField(Document, on_delete=models.CASCADE)
    embedding_vector = models.JSONField()  # Array de floats
    model_version = models.CharField(max_length=64)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

class SemanticQuery(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    query_text = models.TextField()
    query_embedding = models.JSONField()
    results_count = models.IntegerField()
    execution_time = models.FloatField()
    created = models.DateTimeField(auto_now_add=True)
```

### 3. Système E-mail Avancé (paperless_mail_ai/)

Extension du module existant paperless_mail/ :

```python
class MailAIConfiguration(models.Model):
    mail_account = models.OneToOneField(MailAccount, on_delete=models.CASCADE)
    auto_categorization = models.BooleanField(default=True)
    smart_extraction = models.BooleanField(default=True)
    confidence_threshold = models.FloatField(default=0.8)

class MailProcessingResult(models.Model):
    mail_rule = models.ForeignKey(MailRule, on_delete=models.CASCADE)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    extracted_entities = models.JSONField()  # Dates, montants, etc.
    suggested_tags = models.JSONField()
    confidence_score = models.FloatField()
    processing_time = models.FloatField()
```

### 4. Base de données vectorielle (paperless_vector_db/)

```
paperless_vector_db/
├── __init__.py
├── apps.py
├── models.py
├── backends/
│   ├── faiss.py       # FAISS pour recherche locale
│   ├── chroma.py      # ChromaDB alternative
│   └── base.py        # Interface abstraite
├── indexing.py        # Indexation automatique
└── search.py          # Recherche sémantique
```

### 5. Module Agenda Intelligent (paperless_calendar/)

```
paperless_calendar/
├── __init__.py
├── apps.py
├── models.py          # Événements extraits
├── extractors.py      # Extraction de dates/événements
├── integrations/      # Connecteurs calendriers externes
│   ├── caldav.py
│   ├── google.py
│   └── outlook.py
└── tasks.py
```

## APIs REST

### Extension des ViewSets existants

#### 1. DocumentViewSet - Nouvelles actions

```python
@action(detail=True, methods=['post'])
def semantic_search(self, request, pk=None):
    """Recherche sémantique basée sur le contenu du document"""
    pass

@action(detail=True, methods=['get'])
def ai_suggestions(self, request, pk=None):
    """Suggestions IA pour tags, correspondent, type"""
    pass

@action(detail=True, methods=['post'])
def reprocess_ai(self, request, pk=None):
    """Retraitement IA complet du document"""
    pass
```

#### 2. Nouveaux ViewSets

```python
# paperless_ai_engine/views.py
class SemanticSearchViewSet(ViewSet):
    @action(detail=False, methods=['post'])
    def search(self, request):
        """Recherche sémantique globale"""
        pass

class EmbeddingViewSet(ReadOnlyModelViewSet):
    """Gestion des embeddings de documents"""
    pass

# paperless_calendar/views.py
class CalendarEventViewSet(ModelViewSet):
    """Gestion des événements extraits"""
    pass

# paperless_ai_ocr/views.py
class OCRResultViewSet(ReadOnlyModelViewSet):
    """Historique et résultats OCR"""
    pass
```

### Nouvelles routes API

```python
# urls.py additions
api_router.register(r"semantic_search", SemanticSearchViewSet, basename="semantic_search")
api_router.register(r"embeddings", EmbeddingViewSet)
api_router.register(r"calendar_events", CalendarEventViewSet)
api_router.register(r"ocr_results", OCRResultViewSet)
api_router.register(r"ai_config", AIConfigurationViewSet)
```

## Structure de base de données

### Nouvelles tables

```sql
-- Configuration IA
CREATE TABLE paperless_ai_engine_aiconfiguration (
    id SERIAL PRIMARY KEY,
    embedding_model VARCHAR(256) DEFAULT 'distilbert-base-multilingual-cased',
    llm_model_path VARCHAR(512),
    vector_dimension INTEGER DEFAULT 768,
    similarity_threshold FLOAT DEFAULT 0.7,
    enabled BOOLEAN DEFAULT true,
    created TIMESTAMP DEFAULT NOW(),
    updated TIMESTAMP DEFAULT NOW()
);

-- Embeddings de documents
CREATE TABLE paperless_ai_engine_documentembedding (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents_document(id) ON DELETE CASCADE,
    embedding_vector JSONB,
    model_version VARCHAR(64),
    created TIMESTAMP DEFAULT NOW(),
    updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(document_id)
);

-- Index pour recherche vectorielle
CREATE INDEX idx_document_embedding_model ON paperless_ai_engine_documentembedding(model_version);

-- Résultats OCR
CREATE TABLE paperless_ai_ocr_ocrresult (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents_document(id) ON DELETE CASCADE,
    engine VARCHAR(64),
    confidence FLOAT,
    raw_text TEXT,
    bounding_boxes JSONB,
    processing_time FLOAT,
    created TIMESTAMP DEFAULT NOW()
);

-- Configuration OCR
CREATE TABLE paperless_ai_ocr_ocrconfiguration (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128),
    primary_engine VARCHAR(64),
    secondary_engine VARCHAR(64),
    fusion_strategy VARCHAR(64),
    confidence_threshold FLOAT DEFAULT 0.8,
    enabled BOOLEAN DEFAULT true
);

-- Événements de calendrier
CREATE TABLE paperless_calendar_calendarevent (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents_document(id) ON DELETE CASCADE,
    title VARCHAR(256),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    description TEXT,
    extracted_confidence FLOAT,
    external_calendar_id VARCHAR(256),
    created TIMESTAMP DEFAULT NOW()
);

-- Extension mail avec IA
CREATE TABLE paperless_mail_ai_mailaiconfiguration (
    id SERIAL PRIMARY KEY,
    mail_account_id INTEGER REFERENCES paperless_mail_mailaccount(id) ON DELETE CASCADE,
    auto_categorization BOOLEAN DEFAULT true,
    smart_extraction BOOLEAN DEFAULT true,
    confidence_threshold FLOAT DEFAULT 0.8,
    UNIQUE(mail_account_id)
);
```

### Extensions des modèles existants

```python
# Extension du modèle Document
class Document(SoftDeleteModel, ModelWithOwner):
    # Champs existants...

    # Nouveaux champs
    ai_processing_status = models.CharField(
        max_length=32,
        choices=[
            ('pending', 'En attente'),
            ('processing', 'En cours'),
            ('completed', 'Terminé'),
            ('failed', 'Échec')
        ],
        default='pending'
    )
    ai_confidence_score = models.FloatField(null=True, blank=True)
    semantic_summary = models.TextField(blank=True)
    extracted_entities = models.JSONField(default=dict)

    class Meta:
        # Meta existante...
        indexes = [
            # Index existants...
            models.Index(fields=['ai_processing_status']),
            models.Index(fields=['ai_confidence_score']),
        ]
```

## Gestion des ressources

### Configuration système requise

```python
# settings.py additions
AI_ENGINE_CONFIG = {
    'EMBEDDING_MODEL': env.str('PAPERLESS_AI_EMBEDDING_MODEL', 'distilbert-base-multilingual-cased'),
    'LLM_MODEL_PATH': env.str('PAPERLESS_AI_LLM_PATH', '/models/llama3-8b-instruct'),
    'MAX_MEMORY_USAGE': env.int('PAPERLESS_AI_MAX_MEMORY', 4096),  # MB
    'GPU_ENABLED': env.bool('PAPERLESS_AI_GPU', False),
    'BATCH_SIZE': env.int('PAPERLESS_AI_BATCH_SIZE', 8),
}

VECTOR_DB_CONFIG = {
    'BACKEND': env.str('PAPERLESS_VECTOR_BACKEND', 'faiss'),
    'INDEX_TYPE': env.str('PAPERLESS_VECTOR_INDEX_TYPE', 'IndexFlatIP'),
    'DIMENSION': env.int('PAPERLESS_VECTOR_DIMENSION', 768),
}

# Nouvelles tâches Celery
CELERY_TASK_ROUTES = {
    # Tâches existantes...
    'paperless_ai_engine.tasks.*': {'queue': 'ai_processing'},
    'paperless_ai_ocr.tasks.*': {'queue': 'ocr_processing'},
    'paperless_calendar.tasks.*': {'queue': 'calendar_processing'},
}
```

### Monitoring des ressources

```python
class ResourceMonitor:
    def __init__(self):
        self.memory_threshold = settings.AI_ENGINE_CONFIG['MAX_MEMORY_USAGE']

    def check_memory_usage(self):
        """Vérifie l'utilisation mémoire avant traitement IA"""
        pass

    def queue_management(self):
        """Gestion intelligente des files d'attente selon les ressources"""
        pass
```

## Plan de migration

### Phase 1 : Infrastructure de base

1. **Migration 1060** : Ajout des tables de configuration IA
2. **Migration 1061** : Tables embeddings et résultats OCR
3. **Migration 1062** : Extension du modèle Document
4. **Migration 1063** : Tables calendrier et configuration e-mail IA

### Phase 2 : Intégration progressive

1. Installation des dépendances IA
2. Configuration des modèles locaux
3. Mise en place des tâches Celery
4. Tests de compatibilité

### Phase 3 : Migration des données

```python
def migrate_existing_documents():
    """Migration progressive des documents existants vers le nouveau système"""
    for document in Document.objects.filter(ai_processing_status='pending'):
        # Traitement asynchrone via Celery
        process_document_ai.delay(document.id)
```

### Commandes de migration

```bash
# Installation des modèles IA
python manage.py download_ai_models

# Migration des embeddings existants
python manage.py generate_embeddings --batch-size=100

# Retraitement OCR avec nouveau pipeline
python manage.py reprocess_ocr --hybrid --confidence-threshold=0.8
```

## Diagrammes d'architecture

### Architecture générale

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Angular                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │ Dashboard   │ │ Search UI   │ │ AI Config Panel        ││
│  └─────────────┘ └─────────────┘ └─────────────────────────┘│
└─────────────────────────┬───────────────────────────────────┘
                          │ REST API
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend Django                            │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│ │ Core Views  │ │ AI Views    │ │ Extension Views        │ │
│ └─────────────┘ └─────────────┘ └─────────────────────────┘ │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│ │ Documents   │ │ AI Engine   │ │ Vector DB              │ │
│ │ Models      │ │ Models      │ │ Models                 │ │
│ └─────────────┘ └─────────────┘ └─────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Celery Task Queue                          │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│ │ OCR Tasks   │ │ AI Tasks    │ │ Calendar Tasks         │ │
│ │ (Tesseract  │ │ (Embedding, │ │ (Event Extraction)     │ │
│ │ + Doctr)    │ │ LLM)        │ │                        │ │
│ └─────────────┘ └─────────────┘ └─────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Data Layer                                │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│ │ PostgreSQL  │ │ Redis       │ │ Vector Store           │ │
│ │ (Documents, │ │ (Cache,     │ │ (FAISS/ChromaDB)       │ │
│ │ Metadata)   │ │ Sessions)   │ │ (Embeddings)           │ │
│ └─────────────┘ └─────────────┘ └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Pipeline de traitement document

```
┌─────────────┐
│ Nouveau     │
│ Document    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ OCR Hybride │ ◄─── Tesseract + Doctr
│ Pipeline    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Extraction  │ ◄─── DistilBERT Embeddings
│ Sémantique  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Classification│ ◄─── LLaMA 3 Local
│ IA Avancée  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Indexation  │ ◄─── Vector Store + Search Index
│ Multi-modale│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Document    │
│ Finalisé    │
└─────────────┘
```

### Architecture de recherche

```
┌─────────────┐
│ Requête     │
│ Utilisateur │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│ Embedding   │────▶│ Vector      │
│ Query       │     │ Search      │
└─────────────┘     └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Candidats   │
                    │ Similaires  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Re-ranking  │ ◄─── LLaMA 3 Local
                    │ Contextuel  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Résultats   │
                    │ Finaux      │
                    └─────────────┘
```

## Sécurité et permissions

### Extension du système de permissions

```python
# Nouvelles permissions
PAPERLESS_AI_PERMISSIONS = [
    ('can_use_ai_search', 'Can use AI semantic search'),
    ('can_configure_ai', 'Can configure AI settings'),
    ('can_view_ai_results', 'Can view AI processing results'),
    ('can_reprocess_ai', 'Can trigger AI reprocessing'),
]

# Groupes d'utilisateurs
AI_USER_GROUPS = {
    'ai_basic_users': ['can_use_ai_search', 'can_view_ai_results'],
    'ai_power_users': ['can_use_ai_search', 'can_view_ai_results', 'can_reprocess_ai'],
    'ai_administrators': ['can_use_ai_search', 'can_configure_ai', 'can_view_ai_results', 'can_reprocess_ai'],
}
```

### Chiffrement des modèles

```python
class ModelEncryption:
    """Chiffrement des modèles IA locaux pour la sécurité"""

    @staticmethod
    def encrypt_model(model_path: str, key: bytes) -> str:
        """Chiffre un modèle local"""
        pass

    @staticmethod
    def decrypt_model(encrypted_path: str, key: bytes) -> str:
        """Déchiffre un modèle pour utilisation"""
        pass
```

## Tests et validation

### Structure de tests

```
tests/
├── test_ai_engine/
│   ├── test_embeddings.py
│   ├── test_llm.py
│   └── test_search.py
├── test_ocr_hybrid/
│   ├── test_fusion.py
│   └── test_performance.py
├── test_calendar/
│   └── test_extraction.py
└── test_integration/
    ├── test_api.py
    └── test_performance.py
```

### Métriques de performance

```python
class PerformanceMetrics:
    """Collecte de métriques pour optimisation"""

    def track_embedding_time(self, document_id: int, processing_time: float):
        pass

    def track_search_accuracy(self, query: str, relevant_results: int, total_results: int):
        pass

    def track_memory_usage(self, operation: str, memory_mb: float):
        pass
```

Cette architecture technique offre une extension modulaire et scalable de Paperless-ngx, intégrant des capacités d'IA avancées tout en préservant la compatibilité et les performances du système existant.
